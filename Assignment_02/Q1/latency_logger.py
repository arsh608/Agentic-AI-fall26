"""SaafHawa tool-latency logger for Assignment Beta, Question 1, Section 2, item 6.

Each round calls every tool once and appends one row per call to the raw log, so
the pooled median is not skewed by one tool having more measurements.

Run:      python latency_logger.py run --rounds 25 --spacing 10
Summary:  python latency_logger.py summary
"""
import argparse
import csv
import json
import math
import os
import pathlib
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_LOG = HERE / "tool_latency_log.csv"
PKT = timezone(timedelta(hours=5))

# Central Karachi for weather, Clifton Block 1 (an active sea-front station) for OpenAQ.
LAT, LON = 24.8607, 67.0011
OPENAQ_LOCATION_ID = 6346780
OPENAQ_URL = f"https://api.openaq.org/v3/locations/{OPENAQ_LOCATION_ID}/latest"
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=Asia%2FKarachi"
)
# Active Karachi OpenAQ sensors report no PM10, so PM10 comes from this modelled source.
PM10_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={LAT}&longitude={LON}&current=pm10,pm2_5"
)

COLUMNS = [
    "session_id", "round", "timestamp_utc", "timestamp_pkt", "tool",
    "in_pooled_median", "latency_ms", "ok", "http_status", "response_bytes", "detail",
]

QUERIES = [
    "Aj din 12 bajy temperature kitna rise hoga bachon ki school 12 bajy off",
    "Is it safe to go for an evening jog by the sea today",
    "asthma patient smog PM2.5 outside advice",
    "outdoor labourer heatwave water and rest advice",
    "elderly person heatstroke symptoms emergency",
]


def load_openaq_key():
    key = os.environ.get("OPENAQ_API_KEY")
    if key:
        return key
    for name in (".env", ".env.txt"):
        env_file = HERE.parent / name
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                if line.strip().startswith("OPENAQ_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAQ_API_KEY not found in the environment, .env or .env.txt")


def http_tool(url, headers=None):
    """Timed GET with a fresh connection, including the body read and JSON parse."""
    req = urllib.request.Request(url, headers=headers or {})
    start = time.perf_counter_ns()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            payload = json.loads(body)
            status = resp.status
        return (time.perf_counter_ns() - start) / 1e6, True, status, len(body), payload
    except urllib.error.HTTPError as e:
        return (time.perf_counter_ns() - start) / 1e6, False, e.code, 0, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return (time.perf_counter_ns() - start) / 1e6, False, "", 0, None


def heat_index_c(temp_c, rh):
    """US National Weather Service heat index (Rothfusz regression with its adjustments)."""
    t = temp_c * 9 / 5 + 32
    hi = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (hi + t) / 2 >= 80:
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
              - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
              + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95)) / 17)
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
    else:
        hi = (hi + t) / 2
    return (hi - 32) * 5 / 9


def tokenize(text):
    return re.findall(r"[a-z0-9.]+", text.lower())


class KnowledgeBase:
    """BM25 retrieval over the advisory chunks. The index is built once, before timing."""

    def __init__(self, path, k1=1.5, b=0.75):
        self.chunks = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["chunks"]
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(c["text"] + " " + c["roman_urdu_terms"])) for c in self.chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_length = sum(self.lengths) / len(self.lengths)
        doc_freq = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in doc_freq.items()}

    def lookup(self, query, top_k=3):
        scores = []
        for doc, length in zip(self.docs, self.lengths):
            score = 0.0
            for term in tokenize(query):
                f = doc.get(term, 0)
                if f:
                    norm = f + self.k1 * (1 - self.b + self.b * length / self.avg_length)
                    score += self.idf[term] * f * (self.k1 + 1) / norm
            scores.append(score)
        ranked = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
        return [self.chunks[i]["id"] for i in ranked[:top_k]]


def openaq_detail(payload):
    if not payload or not payload.get("results"):
        return "no results"
    r = payload["results"][0]
    return f"sensor={r.get('sensorsId')} value={r.get('value')} at={r['datetime']['utc']}"


def run(args):
    key = load_openaq_key()
    kb = KnowledgeBase(HERE / "knowledge_base.json")
    log_path = pathlib.Path(args.log)
    is_new = not log_path.exists()
    session_id = datetime.now(PKT).strftime("%Y%m%d-%H%M%S")
    temp_c, rh = None, None

    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()

        def record(round_no, tool, pooled, ms, ok, status, size, detail):
            now = datetime.now(timezone.utc)
            writer.writerow({
                "session_id": session_id, "round": round_no,
                "timestamp_utc": now.isoformat(timespec="seconds"),
                "timestamp_pkt": now.astimezone(PKT).isoformat(timespec="seconds"),
                "tool": tool, "in_pooled_median": "yes" if pooled else "no",
                "latency_ms": f"{ms:.6f}", "ok": "yes" if ok else "no",
                "http_status": status, "response_bytes": size, "detail": detail,
            })
            f.flush()

        for i in range(1, args.rounds + 1):
            ms, ok, status, size, payload = http_tool(OPENAQ_URL, {"X-API-Key": key})
            record(i, "air_quality_openaq", True, ms, ok, status, size, openaq_detail(payload))

            ms, ok, status, size, payload = http_tool(WEATHER_URL)
            detail = "no data"
            if ok:
                cur = payload["current"]
                temp_c, rh = cur["temperature_2m"], cur["relative_humidity_2m"]
                detail = f"temp_c={temp_c} rh={rh} wind_kmh={cur['wind_speed_10m']}"
            record(i, "weather_openmeteo", True, ms, ok, status, size, detail)

            ms, ok, status, size, payload = http_tool(PM10_URL)
            detail = "no data"
            if ok:
                cur = payload["current"]
                detail = f"modelled pm10={cur['pm10']} pm2_5={cur['pm2_5']}"
            record(i, "pm10_openmeteo_supplementary", False, ms, ok, status, size, detail)

            if temp_c is not None:
                start = time.perf_counter_ns()
                hi = heat_index_c(temp_c, rh)
                ms = (time.perf_counter_ns() - start) / 1e6
                record(i, "heat_index_local", True, ms, True, "", "", f"heat_index_c={hi:.2f}")

            query = QUERIES[(i - 1) % len(QUERIES)]
            start = time.perf_counter_ns()
            hits = kb.lookup(query)
            ms = (time.perf_counter_ns() - start) / 1e6
            record(i, "kb_lookup_local", True, ms, True, "", "", "|".join(hits))

            print(f"round {i}/{args.rounds} done", flush=True)
            if i < args.rounds:
                time.sleep(args.spacing)


def summary(args):
    with open(args.log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_tool = defaultdict(list)
    failed = Counter()
    days = defaultdict(set)
    for r in rows:
        if r["ok"] == "yes":
            by_tool[r["tool"]].append(float(r["latency_ms"]))
            days[r["tool"]].add(r["timestamp_pkt"][:10])
        else:
            failed[r["tool"]] += 1
    for tool, values in sorted(by_tool.items()):
        print(f"{tool}: n={len(values)} failed={failed[tool]} days={sorted(days[tool])} "
              f"median={statistics.median(values):.4f} ms "
              f"min={min(values):.4f} max={max(values):.4f}")
    pooled = [float(r["latency_ms"]) for r in rows
              if r["ok"] == "yes" and r["in_pooled_median"] == "yes"]
    print(f"POOLED median (four required tools): n={len(pooled)} {statistics.median(pooled):.4f} ms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--rounds", type=int, default=25)
    p_run.add_argument("--spacing", type=float, default=10.0)
    p_run.add_argument("--log", default=str(DEFAULT_LOG))
    p_run.set_defaults(func=run)
    p_summary = sub.add_parser("summary")
    p_summary.add_argument("--log", default=str(DEFAULT_LOG))
    p_summary.set_defaults(func=summary)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
