# EventLoom

**Live event discovery with explainable entity resolution.** A full-stack portfolio project built around two marketplace problems: reconciling inconsistent provider listings and helping people find relevant events quickly.

React + TypeScript · Python + FastAPI · RapidFuzz · SQLAlchemy · SQLite / PostgreSQL · Docker

All event schedules, providers, prices, availability, and labels are **synthetic**. The project has no affiliation with SeatGeek and does not sell tickets.

## Run it

Install **Python 3.11 or newer**, unzip the project, and open a terminal in this folder:

```bash
python scripts/run.py
```

On Windows, use `py scripts/run.py` if `python` is not available. The launcher creates a project virtual environment, installs the pinned dependencies, seeds the catalog, and starts the server. First-time setup requires an internet connection for Python packages and takes a few minutes. A compiled frontend is included; Node is not required to run it.

Open **http://localhost:8000**. Interactive API documentation is at **http://localhost:8000/docs**. Stop the server with Ctrl+C. A later launch preserves the local database.

Use `python scripts/run.py --port 8001` for a different port, or `--no-serve` to install and seed only.

## What is implemented

- **Event entity resolution:** Unicode/punctuation normalization, city aliases, order-independent sports titles, timezone normalization, adjacent-day candidate blocking, weighted title/venue/time scoring, confidence thresholds, and a runner-up margin. Ambiguous or insufficient evidence produces a persisted review record rather than an automatic link.
- **Search:** inverted trigram retrieval, typo-tolerant field-aware ranking, city/category/date/price filters, deterministic pagination, relevance/price sorting, and a bounded 128-query ranking cache. Current availability and prices are applied after cached text ranking on every request.
- **Product interface:** responsive discovery pages, event details, provider offer comparison, saved events in local storage, loading/error/empty states, keyboard-operable controls, native modal focus handling, and an interactive matching inspector.
- **Inventory ingestion:** authenticated provider updates, composite provider/listing identity, integer-cent prices, validated quantities, timezone-aware versions, atomic conditional upserts, out-of-order update rejection, idempotent retries, and read-model invalidation after accepted writes.
- **Engineering evidence:** event-disjoint development/test sets, exact-match and linear-search baselines, threshold selection on development data, per-noise quality results, failure samples, fixture hashes, raw latency samples, automated backend tests, a browser workflow test, and CI configuration.

## Measured results

| Measurement | Result | Scope |
|---|---:|---|
| Catalog / source observations | 12,000 / 37,200 | Seed 42 synthetic fixture |
| Held-out known-event recall | **86.36%** | 28,701 known observations; exact-match baseline 25.56% |
| Accepted-link precision | **100% observed** | 24,787 accepted links; zero observed false merges, not a real-world guarantee |
| Candidate comparisons avoided | **99.84%** | 567,849 comparisons versus 355,716,000 exhaustive comparisons |
| Typo-query hit@10 | **100%** | 300 generated transposition queries; title-level relevance |
| Cold indexed search vs linear scan | **4.35× median speedup** | Same ranker, cold cache, local microbenchmark |
| Warm-cache HTTP throughput | **115 requests/s** | 800 requests, 8 concurrent clients, fixed ten-query mix |
| Warm-cache HTTP p95 | **132.6 ms** | Real localhost HTTP, one Uvicorn process, zero errors |

The data generator deliberately includes incomplete titles, time drift, aliases, spelling noise, and unknown events. These are controlled simulations; they do not establish performance on actual ticket marketplaces. Timing depends on hardware, query distribution, cache state, and load. Read [the measurement report](docs/BENCHMARKS.md) before using the numbers.

## Explore the demo

1. Search `Velvt Echoes` and compare the matching titles.
2. Filter to Seattle, select a category, or set a price/date range.
3. Open an event to inspect available offers. Save an event, reload, and open **Saved**.
4. Open **Matching lab**. A decorated provider title should match the reference event. Replace it with an unrelated artist to see abstention.
5. Inspect `/docs`, then try the matching endpoint with a timezone offset or reversed sports team names.

Saved events are local browser snapshots, not user accounts or reservations. There is no checkout.

## Develop

After the launcher finishes, activate the project environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Then:

```bash
# Backend tests
pytest backend/tests -q

# Reproduce matching evaluation and select the configuration on DEV only
python scripts/benchmark.py

# Cold-cache indexed-vs-linear search benchmark
python scripts/search_benchmark.py

# Start a temporary local server and benchmark actual HTTP
python scripts/verify_http.py --requests 800 --concurrency 8
```

To edit the interface, install **Node 22+**:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to the backend at port 8000. Run `npm run build` to replace the compiled interface served by FastAPI. The launcher serves that compiled build.

For browser tests, first seed the database and build the frontend, then run:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Playwright configuration starts a temporary API on port 8766. It finds the project's virtualenv automatically. On systems without a `python` command, start the API yourself using `py scripts/e2e_server.py` and then run the browser test.

## PostgreSQL and Docker

```bash
docker compose up --build
```

This config runs the same application with PostgreSQL 16, a persistent database volume, health checks, and a non-root app container. Its database credentials are local demo defaults; the database port is not exposed. Only localhost can reach the published app port.

SQLite and the complete browser workflow were exercised in the build environment. Docker execution and the PostgreSQL integration test could not run there. The dedicated PostgreSQL test is wired into CI using a disposable database; do not represent that configuration as a verified cloud deployment.

To test your own disposable PostgreSQL instance, set `TEST_DATABASE_URL` to a SQLAlchemy psycopg connection URL and run `pytest backend/tests/test_postgres.py -q`. The test creates and drops a randomly named schema; it does not use production tables.

## Ingestion and review

`POST /api/match` is a read-only matching preview. `POST /api/ingest`, `GET /api/review`, and `GET /api/metrics` require `X-Admin-Token` matching the server's `ADMIN_TOKEN`. Without a configured token, those endpoints return 503. Set the environment variable before starting the app; the Python launcher does not load `.env` files. Docker Compose can read `.env`.

The fixture contains examples in `data/observations.jsonl`. Submit only an entry's `listing` object. Equal or older `updated_at` values produce `applied: false`; equal-time conflicting payloads intentionally keep the first accepted version.

Review records are inspectable through the admin API. A reviewer approval interface is outside this version's scope.

## Structure

| Path | Purpose |
|---|---|
| `backend/eventloom/matching.py` | Blocking, scoring, confidence, and explanations |
| `backend/eventloom/search.py` | Trigram postings, ranking cache, filters, pagination |
| `backend/eventloom/store.py` | Persistence and atomic provider-version upserts |
| `backend/eventloom/api.py` | HTTP validation, authentication, read models, timing |
| `backend/eventloom/generate.py` | Reproducible synthetic fixture |
| `frontend/src/` | React/TypeScript interface and responsive styles |
| `backend/tests/`, `frontend/tests/` | Regression and browser tests |
| `scripts/` | Startup, evaluation, and real-HTTP load tooling |
| `benchmarks/` | Raw results, configuration, hashes, and run logs |
| `docs/` | Architecture, measurements, resume bullets, interview guide |

## Boundaries and next work

This is a complete **local engineering demo**, not a production ticketing service. The canonical catalog is immutable while the server runs. The text index and inventory read model are in process, so run **one worker** and route inventory writes through this app. Independent writers or multiple replicas need shared invalidation/versioning before deployment. Provider feeds are simulated; importing real feeds needs an authorized connector, provenance, scheduling, and deletion/reschedule policies.

There is no Elasticsearch, Redis, learned model, LLM agent, Kubernetes deployment, or AWS deployment in this implementation. Those are possible future extensions and should not be listed as completed work. The most valuable next validation is a manually labeled, authorized real-data matching set with hard negatives, cancellations, venue aliases, and rescheduled events.
