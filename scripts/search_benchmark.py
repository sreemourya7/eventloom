"""Search ranking quality and indexed-vs-linear latency on the exact same fixture/query set."""

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from eventloom.matching import normalize
from eventloom.search import SearchIndex, relevance


def percentile(values, fraction=0.95):
    return sorted(values)[int(fraction * (len(values) - 1))]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    p.add_argument("--output", default="benchmarks")
    p.add_argument("--queries", type=int, default=300)
    a = p.parse_args()
    events = json.loads((Path(a.data) / "events.json").read_text())
    index = SearchIndex(events)
    rng = random.Random(77)
    queries = []
    for e in rng.choices(events, k=a.queries):
        title = e["title"]
        pos = max(1, len(title) // 2)
        # Deterministic adjacent-character typo; no query-specific tuning.
        q = title[:pos] + title[pos + 1] + title[pos] + title[pos + 2 :]
        queries.append((q, normalize(title)))
    indexed_times, linear_times, examined = [], [], []
    indexed_hits = linear_hits = 0
    for q, relevant in queries:
        index.rank.cache_clear()  # Measure cold ranking even for repeated titles.
        start = time.perf_counter()
        result = index.search(q=q, size=10)
        indexed_times.append((time.perf_counter() - start) * 1000)
        indexed_hits += any(normalize(e["title"]) == relevant for e in result["items"])
        examined.append(result["candidates_examined"])
        start = time.perf_counter()
        norm = normalize(q)
        scored = [
            (relevance(norm, *index.fields[key], doc), index.events[key])
            for key, doc in index.docs.items()
        ]
        scored = [(score, e) for score, e in scored if score >= 58]
        scored.sort(key=lambda row: (-row[0], row[1]["starts_at"], row[1]["id"]))
        linear_times.append((time.perf_counter() - start) * 1000)
        linear_hits += any(normalize(e["title"]) == relevant for _, e in scored[:10])
    report = dict(
        events=len(events),
        queries=len(queries),
        seed=77,
        relevance="At least one top-10 result has the exact source title; one deterministic adjacent transposition per query",
        indexed_hit_at_10=indexed_hits / len(queries),
        linear_hit_at_10=linear_hits / len(queries),
        indexed_p50_ms=statistics.median(indexed_times),
        indexed_p95_ms=percentile(indexed_times),
        linear_p50_ms=statistics.median(linear_times),
        linear_p95_ms=percentile(linear_times),
        p50_speedup=statistics.median(linear_times) / statistics.median(indexed_times),
        mean_candidates=statistics.mean(examined),
        raw_indexed_ms=indexed_times,
        raw_linear_ms=linear_times,
        note="Cold ranking cache per query; sequential in-process microbenchmark, no DB/HTTP cost, generated queries, not real user relevance judgments",
    )
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "search.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if not k.startswith("raw_")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
