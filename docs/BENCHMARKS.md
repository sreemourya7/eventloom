# Reproducible measurements

Recorded during the November 6, 2026 build (Pacific time). All quality labels, schedules, prices, and provider feeds are synthetic. Raw results live in `benchmarks/`.

## Matching quality

| Quantity | Value |
|---|---:|
| Canonical catalog | 12,000 events |
| All observations | 37,200 |
| Development observations | 7,557 |
| Held-out observations | 29,643 |
| Held-out known observations | 28,701 |
| Held-out unknown observations | 942 |
| Correct accepted links | 24,787 |
| False merges observed | 0 |
| Precision among accepted links | 100.00% observed |
| Recall among known observations | 86.36% |
| F1 | 0.9268 |
| Exact-field baseline recall | 25.56% |
| Recall improvement | 60.80 percentage points / 3.38× |
| Candidate comparisons | 567,849 |
| Exhaustive comparison count | 355,716,000 |
| Candidate comparisons avoided | 99.8404% |
| Offline matching throughput | 2,067 observations/s |
| Offline match p95 | 0.907 ms |

The headline measurement scores held-out observations against the **full 12,000-event catalog**, retaining development events as extra distractors. `matching.json` also reports a test-only catalog run.

Events are split by SHA256(event_id) modulo ten: buckets 0–1 development and 2–9 test. All provider variants of an event share its split. The development grid is threshold 0.82/0.85/0.88/0.91/0.94 and margin 0.02/0.04/0.06. Selection maximizes development F1 subject to precision ≥99.5% when feasible. The chosen threshold/margin is **0.82 / 0.06**. The held-out labels do not choose these values.

The baseline requires matching normalized title, venue, city, and the original timestamp string. It deliberately represents a strict record-equality approach; it does not implement timezone normalization or aliases. Its weakness is visible rather than hidden. The candidate-reduction denominator is a computed exhaustive comparison count, **not a timed brute-force run or an end-to-end speedup claim**.

Zero observed errors in 24,787 accepted assignments does not imply perfect precision outside this dataset. 3,914 known observations were not recovered. Missing title information and two-hour time drift dominate those misses.

### Results by source noise

| Noise | Observations | Known-event recall | Accepted false merges |
|---|---:|---:|---:|
| clean | 7,310 | 100.00% | 0 |
| decorated | 7,185 | 100.00% | 0 |
| drift | 1,435 | 52.75% | 0 |
| missing | 2,838 | 8.10% | 0 |
| offset | 4,248 | 100.00% | 0 |
| typo | 5,685 | 88.95% | 0 |
| unknown | 942 | N/A — unknown events | 0 |

All 942 held-out unknown observations were rejected. Unknown negatives have unrelated performer names and are easier than many real hard negatives. Event slots also avoid genuine simultaneous venue collisions. There is no manually labeled real-data holdout, reschedule/cancellation model, broad venue-alias taxonomy, multilingual evaluation, or open-world identity guarantee. `errors.json` contains the first 100 failed assignments for inspection.

## Search quality and cold ranking latency

| Quantity | Result |
|---|---:|
| Generated typo queries | 300 |
| Indexed title-level hit@10 | 100.00% |
| Linear title-level hit@10 | 100.00% |
| Cold indexed p50 | 26.68 ms |
| Cold indexed p95 | 59.39 ms |
| Linear p50 | 116.14 ms |
| Linear p95 | 176.26 ms |
| Median latency speedup | 4.35× |
| Mean indexed candidates | 2,553.3 / 12,000 |

Seed 77 samples event titles and applies one deterministic adjacent-character transposition. A hit means at least one of the top ten results has the same normalized source title. Multiple events can share a title, and the sampled query set can contain repetitions. This measures a narrow title-retrieval task, not user satisfaction, personalization, or event-ID recall.

The ranking cache is cleared **before each timed indexed query**. Linear scan and indexed retrieval use the same field-aware scorer; the scan evaluates every document. Both runs are sequential and in process, excluding HTTP/database costs. Raw per-query times are included in `search.json`.

## Real HTTP benchmark

| Quantity | Result |
|---|---:|
| Measured requests | 800 |
| Concurrent clients | 8 |
| Measured duration | 6.96 seconds |
| Throughput | 115.00 requests/s |
| p50 | 64.10 ms |
| p95 | 132.56 ms |
| p99 | 193.24 ms |
| HTTP/validation errors | 0 |

One Uvicorn process, real HTTP over localhost, eight closed-loop clients, a fixed ten-query mix, and 30 warmup requests. The 128-entry ranking cache is **warm**; current inventory filtering and response serialization still run. This is a short local run, not a sustained saturation test or deployment capacity forecast. No cloud, TLS, external network, or production traffic was involved. Do not combine this warm-cache number with the cold ranking latency as though they were the same workload.

Runtime: Python 3.12.14 on Linux-6.18.57-x86_64-with-glibc2.39, shared execution environment. CPU allocation and neighboring load were not controlled. Timing metrics will vary across machines and runs. `http.json` contains all 800 individual request samples, status codes, and validity flags.

## Verification

- 23 backend tests passed: normalization, timezone offsets, sports title reversal, different showtimes, ambiguity, unknown events, validation, concurrent provider updates, stale/replayed versions, source-scoped identity, review isolation, filter pagination, live-price cache correctness, authentication, and API behavior.
- One PostgreSQL integration test is skipped without `TEST_DATABASE_URL`. A PostgreSQL service and this test are configured in CI, but that CI job was not executed during this build.
- The committed Playwright workflow passed: discovery, saved persistence, event details, matching explanation, typo search, city/budget filtering, 390px layout, and no browser page errors. A temporary configuration selected the available Chromium binary; portable default browser configuration is included.
- Strict TypeScript compilation, Vite production build, Python compilation, and Ruff's selected lint rules passed.
- The cross-platform launcher created a fresh project environment, installed the lockfile, and reused the previously validated seeded database successfully. Windows-specific execution and Docker were not available for direct verification.

## Reproduce

Run these commands from the project root after activating the virtual environment:

```bash
python -m eventloom.generate --events 12000 --seed 42 --output data
python scripts/benchmark.py
python scripts/search_benchmark.py
python scripts/verify_http.py --requests 800 --concurrency 8
pytest backend/tests -q
```

Matching evaluation rewrites `benchmarks/matcher_config.json`. The API loads it at startup; restart after changing it. A previously seeded database retains earlier decisions. For a newly selected policy, create a **new database**, seed it with `python -m eventloom.seed --database-url sqlite:///new-evaluation.db`, and point the API's `DATABASE_URL` at that database. Preserve an existing database if it contains updates you need.

Fixture integrity:

| File | SHA256 |
|---|---|
| events.json | `27fe79ad3de897ac283a09cff390a5da6a43d6ccfaa08f50f06add24d1d8aee5` |
| observations.jsonl | `0616939cf32fc5cc1b3073243eaf58795925724c088c6b5445740656c60a2211` |
