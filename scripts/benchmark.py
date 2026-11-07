"""Offline entity-resolution evaluation. Development chooses thresholds; test stays held out."""

import argparse
import hashlib
import json
import platform
import statistics
import time
from collections import Counter
from pathlib import Path

from eventloom.matching import Matcher, normalize


def summarize(results):
    counts = Counter()
    for gold, predicted, _ in results:
        counts["total"] += 1
        if gold is not None:
            counts["known"] += 1
        else:
            counts["unknown"] += 1
        if predicted is not None:
            counts["accepted"] += 1
            counts["correct" if predicted == gold else "false_merges"] += 1
        if gold is None and predicted is None:
            counts["correct_unknown_abstentions"] += 1
    p = counts["correct"] / max(1, counts["accepted"])
    r = counts["correct"] / max(1, counts["known"])
    return {
        **dict(counts),
        "precision": p,
        "recall": r,
        "f1": 2 * p * r / (p + r) if p + r else 0,
        "false_merge_rate": counts["false_merges"] / max(1, counts["total"]),
    }


def run(events, observations, threshold, margin):
    matcher = Matcher(events, threshold, margin)
    start = time.perf_counter()
    results, times, evaluated = [], [], 0
    for row in observations:
        t = time.perf_counter()
        decision = matcher.match(row["listing"])
        times.append((time.perf_counter() - t) * 1000)
        evaluated += decision["candidate_count"]
        results.append((row["gold_event_id"], decision["event_id"], row["noise"]))
    elapsed = time.perf_counter() - start
    metrics = summarize(results)
    metrics.update(
        seconds=elapsed,
        observations_per_second=len(observations) / elapsed,
        match_p50_ms=statistics.median(times),
        match_p95_ms=sorted(times)[int(0.95 * (len(times) - 1))],
        candidate_comparisons=evaluated,
        brute_force_comparisons=len(events) * len(observations),
        candidate_reduction=1 - evaluated / (len(events) * len(observations)),
    )
    metrics["by_noise"] = {
        noise: summarize([r for r in results if r[2] == noise])
        for noise in sorted({r[2] for r in results})
    }
    errors = [
        dict(gold=g, predicted=p, noise=n)
        for g, p, n in results
        if (g is not None and p != g) or (g is None and p is not None)
    ]
    return metrics, errors


def baseline(events, rows):
    index = {
        (
            normalize(e["title"]),
            normalize(e["venue"]),
            normalize(e["city"]),
            e["starts_at"],
        ): e["id"]
        for e in events
    }
    result = []
    for row in rows:
        e = row["listing"]
        predicted = index.get(
            (
                normalize(e["title"]),
                normalize(e["venue"]),
                normalize(e["city"]),
                e["starts_at"],
            )
        )
        result.append((row["gold_event_id"], predicted, row["noise"]))
    return summarize(result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    p.add_argument("--output", default="benchmarks")
    args = p.parse_args()
    data, output = Path(args.data), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    events = json.loads((data / "events.json").read_text())
    observations = [
        json.loads(line)
        for line in (data / "observations.jsonl").read_text().splitlines()
    ]
    dev_events = [e for e in events if e["split"] == "dev"]
    test_events = [e for e in events if e["split"] == "test"]
    dev_rows = [r for r in observations if r["split"] == "dev"]
    test_rows = [r for r in observations if r["split"] == "test"]
    assert not {e["id"] for e in dev_events} & {e["id"] for e in test_events}
    # Cache unthresholded rankings once. Grid selection uses DEV only, never test labels.
    dev_matcher = Matcher(dev_events)
    ranked_dev = [(r, dev_matcher.match(r["listing"])) for r in dev_rows]
    trials = []
    for threshold in (0.82, 0.85, 0.88, 0.91, 0.94):
        for margin in (0.02, 0.04, 0.06):
            result = []
            for row, d in ranked_dev:
                top = d["candidates"][0] if d["candidates"] else None
                prediction = (
                    top["event_id"]
                    if top and top["score"] >= threshold and d["margin"] >= margin
                    else None
                )
                result.append((row["gold_event_id"], prediction, row["noise"]))
            m = summarize(result)
            trials.append(dict(threshold=threshold, margin=margin, **m))
    qualified = [t for t in trials if t["precision"] >= 0.995]
    best = max(
        qualified or trials,
        key=lambda t: (t["f1"], t["precision"], t["threshold"], t["margin"]),
    )
    config = {
        "threshold": best["threshold"],
        "margin": best["margin"],
        "selection": "dev F1 with precision >= 0.995 when feasible",
    }
    (output / "matcher_config.json").write_text(json.dumps(config, indent=2))
    test, errors = run(test_events, test_rows, best["threshold"], best["margin"])
    # Also test against the full catalog: denser candidate pool is a more realistic stress case.
    full, full_errors = run(events, test_rows, best["threshold"], best["margin"])
    report = dict(
        dataset=json.loads((data / "manifest.json").read_text()),
        environment=dict(
            python=platform.python_version(),
            system=platform.platform(),
            cpu=platform.processor(),
        ),
        hashes={
            name: hashlib.sha256((data / name).read_bytes()).hexdigest()
            for name in ["events.json", "observations.jsonl"]
        },
        config=config,
        dev=best,
        test=test,
        full_catalog_test=full,
        baseline=baseline(events, test_rows),
        dev_trials=trials,
    )
    (output / "matching.json").write_text(json.dumps(report, indent=2))
    (output / "errors.json").write_text(json.dumps(full_errors[:100], indent=2))
    print(
        json.dumps(
            {k: report[k] for k in ["config", "baseline", "test", "full_catalog_test"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
