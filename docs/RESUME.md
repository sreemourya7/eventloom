# Resume-ready project entry

**EventLoom — Live Event Discovery & Entity Resolution**  
Python, FastAPI, React, TypeScript, SQLAlchemy, SQLite, RapidFuzz

- Built a full-stack event discovery platform indexing **12,000 synthetic events** and reconciling **37,200 provider observations** across eight cities, with typo-tolerant search, live inventory filters, offer comparison, and a responsive React/TypeScript interface.
- Engineered explainable event matching with geographic/temporal candidate blocking and confidence-based abstention; improved synthetic held-out recall from **25.6% to 86.4%** while avoiding **99.84%** of exhaustive comparisons and observing zero false merges across **24,787** accepted links.
- Implemented atomic version-guarded SQL upserts, retry deduplication, and bounded search-ranking caching; measured **115 requests/s** at **133 ms p95** across 800 localhost requests with eight concurrent clients and a warmed cache.

## Alternative search-focused bullet

- Built a trigram inverted index with field-aware fuzzy ranking, reducing median cold-query latency **4.4×** versus a linear scan while preserving **100% title-level hit@10** across 300 generated typo queries over a 12,000-event catalog.

## Claim boundaries

Keep “synthetic,” “local,” and “warm cache” where appropriate. The project does not demonstrate actual SeatGeek inventory, production traffic, user conversion, commercial integrations, learned-model quality, or AWS deployment. PostgreSQL/Docker configuration and a dedicated integration test are included, but verify them on your machine before describing that deployment as tested.

Read `INTERVIEW_GUIDE.md`, reproduce the runs, and understand the matching and upsert code before discussing the project in interviews.
