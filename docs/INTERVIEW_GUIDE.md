# Interview walkthrough

## A concise opening

“I built EventLoom to reconcile inconsistent listings into a canonical live-event catalog and make those events searchable. The core work is entity resolution, typo-tolerant retrieval, and safe inventory updates. I evaluated it on a seeded synthetic dataset with event-disjoint development and test sets, and built a React interface that exposes matching decisions.”

Read and run the project before presenting it as your work. Be ready to explain the implementation and its limits.

## Demonstrate in five minutes

1. Open discovery, search `Velvt Echoes`, and filter by city or budget.
2. Show provider offers and saved-event persistence.
3. Open Matching lab. Compare a decorated title against an unrelated performer.
4. Explain why an ambiguous candidate must be held for review.
5. Open `benchmarks/matching.json`, show exact-match recall and candidate-comparison counts, then discuss the controlled synthetic setup.
6. Show the atomic upsert and the concurrent-version regression test.

## Questions worth preparing

**Why blocking before fuzzy matching?** An exhaustive catalog scan grows with every event. City and UTC-day neighborhoods discard geographically or temporally implausible pairs while retaining near-midnight candidates. Measure the reduction in comparisons rather than claiming the same factor as an end-to-end speedup.

**Why not accept every highest-scoring candidate?** There is always a highest score, even when no event is correct. Thresholding rejects weak evidence; a runner-up margin rejects ambiguity. False merges pollute prices and inventory, so precision matters.

**Why 86.4% recall rather than nearly 100%?** Missing performer names and two-hour timing drift frequently lack enough evidence for a safe link. The per-noise report makes this explicit. Increasing recall at any cost would undermine inventory trust.

**Why 100% observed precision needs qualification?** This is one controlled generated dataset with a simple schedule and a limited alias/typo distribution. Zero observed false merges does not demonstrate zero real-world error. Validate against manually labeled real provider data and hard negatives before deployment.

**How did you prevent evaluation leakage?** Hash whole event IDs into development/test groups. All source variants of an event stay together. Choose threshold/margin on development labels only, then score test observations against both a test-only and a full catalog.

**Why not use an LLM?** Normalization, fuzzy similarity, temporal evidence, and explicit gates solve this controlled version cheaply and deterministically. An LLM could assist difficult alias cases, but would need grounding, a held-out evaluation, cost controls, and failure analysis. It is not part of this implementation.

**How do retries avoid corrupting inventory?** Composite provider identity deduplicates updates. A database-level conditional upsert allows only strictly newer UTC versions, including when concurrent requests arrive in a different order.

**Why cache ranking rather than entire responses?** Event text is immutable, while inventory prices and quantities change. Caching just relevance preserves the expensive fuzzy work while applying current inventory on each request.

**How would this scale to multiple replicas?** Externalize or version the index and inventory view, propagate invalidation, and use durable catalog import jobs. The current application explicitly uses one worker; do not claim distributed cache coherence.

**What does the latency number mean?** A short real-HTTP localhost run with eight closed-loop clients and a warmed ten-query cache. It is neither a production SLA nor an AWS benchmark. Compare the separate cold ranking microbenchmark before discussing caching benefits.

## Ownership and scope

This project contains actual code and measured results, but it is still generated-data engineering work. Do not claim real customers, commercial provider integrations, ticket sales, production deployment, business conversion gains, learned-model accuracy, or infrastructure that is absent from the source.
