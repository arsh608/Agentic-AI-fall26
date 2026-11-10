# Q1 model research notes (access date for everything below: 2026-11-04)

Working notes only, not a submission file. Every value must trace to a page listed here.

## Parameters for roll number 23k-0078
R = 78, D = (2+3+0+0+7+8) mod 10 = 20 mod 10 = 0.
Q = 3,450; N = 7; p = 0.04; H = 6; B = $1,980; T = 10 s.

## Prices per 1M tokens (input / cached read / output)
Anthropic, https://platform.claude.com/docs/en/about-claude/pricing
- Claude Haiku 5.5 (prompts up to 100k): 0.10 / 0.01 / 0.50; 5m cache write 0.125; 1h cache write 0.20
- Claude Sonnet 5.5: 2.00 / 0.10 / 10.00; 5m cache write 2.50; 1h cache write 4.00
- Claude Opus 5.5: 4.00 / 0.20 / 20.00; 5m cache write 5.00; 1h cache write 8.00

OpenAI, https://developers.openai.com/api/docs/pricing (Standard tier, up to 272k input)
- gpt-6-luna: 0.10 / 0.01 / 0.50
- gpt-6.1-terra: 1.00 / 0.05 / 5.00
- gpt-6.1-sol: 2.00 / 0.10 / 10.00
- gpt-5.4-nano: 0.20 / 0.02 / 1.25

Google, https://aistudio.google.com/docs/pricing (paid tier)
- Gemini 3.5 Flash-Lite: 0.30 / 0.03 / 2.50; storage 1.00 per 1M tokens per hour
- Gemini 3.1 Flash-Lite: 0.25 / 0.025 / 1.50; storage 1.00 per 1M tokens per hour
- Gemini 3.8 Flash: 0.75 / 0.075 / 3.75 through 2026-12-31, then 1.50 / 0.15 / 7.50; storage 0.50, then 1.00

## Artificial Analysis pages: reasoning warning
Default model pages measure the "max" reasoning variant, so their TTFT is NOT usable. The assignment
requires the lowest setting, so use a low or non-reasoning variant page, or state the gap.
- claude-haiku-5-5 (max): 256 tok/s, first answer token 186.19 s, Intelligence Index 36, 1M context, parameters not disclosed
- gpt-6-luna (max): 103 tok/s, first answer token 69.18 s, Intelligence Index 28 (v5.0.1), 1M context, parameters not disclosed
- deepseek-v4-1-flash (max): 189 tok/s, first answer token 36.35 s, median 0.30 / 1.20, 98% cache discount, MIT, 552B total, 16B active, 19 providers
Methodology: speed and latency average each endpoint's runs over the past 5 days.

## Open-weight candidates (from https://artificialanalysis.ai/models/open-source)
DeepSeek V4.1 Flash 1017, GLM-5.3 (Z AI), MiniMax-M3.1-Flash, Qwen3.8 27B (Apache 2.0 per Hugging Face),
Mistral Large 4, Muse Spark Open (Meta), Nemotron 3.5 Super VL (NVIDIA), Beam 1.0 (Reflection).

## Tool-use benchmark
BFCL v4 via https://benchlm.ai/benchmarks/bfclV4 (page updated 2026-11-04): an aggregator table, with no
date or verification status per row, and it covers few of the candidates. Official leaderboard to check:
https://gorilla.cs.berkeley.edu/leaderboard.html

## Karachi sensor finding (OpenAQ, queried 2026-11-04, 25 km radius)
53 locations found. Every location active in the last 30 days reports PM2.5 only. The PM10 sensors found
last reported in 2024. Logger therefore uses OpenAQ for measured PM2.5 and the Open-Meteo Air Quality API
(CAMS model forecast) for modelled PM10, labelled as modelled.
