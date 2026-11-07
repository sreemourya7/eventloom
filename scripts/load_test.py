"""Actual localhost HTTP benchmark: closed-loop concurrency, raw per-request samples."""

import argparse
import asyncio
import json
import platform
import time
from pathlib import Path

import httpx

QUERIES = [
    "Velvet Echoes",
    "Neon",
    "Falcons",
    "Lunar",
    "Quiet",
    "Silver",
    "Electric",
    "Comets",
    "Midnight",
    "Golden",
]


async def measure(base, requests, concurrency):
    samples = []
    async with httpx.AsyncClient(
        base_url=base,
        timeout=60,
        trust_env=False,
        limits=httpx.Limits(max_connections=concurrency),
    ) as client:
        health = (await client.get("/api/health")).json()
        for i in range(30):
            (
                await client.get(
                    "/api/events", params={"q": QUERIES[i % len(QUERIES)], "size": 12}
                )
            ).raise_for_status()
        queue = asyncio.Queue()
        for i in range(requests):
            queue.put_nowait(i)

        async def worker():
            while True:
                try:
                    i = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                start = time.perf_counter()
                try:
                    response = await client.get(
                        "/api/events",
                        params={"q": QUERIES[i % len(QUERIES)], "size": 12},
                    )
                    status = response.status_code
                    valid = status == 200 and isinstance(
                        response.json().get("items"), list
                    )
                except Exception:
                    status, valid = 0, False
                samples.append(
                    dict(
                        ms=(time.perf_counter() - start) * 1000,
                        status=status,
                        valid=valid,
                    )
                )

        start = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(concurrency)))
        elapsed = time.perf_counter() - start
    latencies = sorted(s["ms"] for s in samples)
    report = dict(
        requests=requests,
        concurrency=concurrency,
        elapsed_seconds=elapsed,
        requests_per_second=requests / elapsed,
        errors=sum(not s["valid"] for s in samples),
        p50_ms=latencies[int((len(latencies) - 1) * 0.5)],
        p95_ms=latencies[int((len(latencies) - 1) * 0.95)],
        p99_ms=latencies[int((len(latencies) - 1) * 0.99)],
        catalog=health,
        samples=samples,
        environment=platform.platform(),
        python=platform.python_version(),
        methodology="One warmed Uvicorn process with bounded rank cache, real HTTP over localhost, fixed 10-query mix, closed-loop concurrency; no AWS or production traffic",
    )
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--requests", type=int, default=800)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--output", default="benchmarks/http.json")
    a = p.parse_args()
    if a.requests < 1 or a.concurrency < 1:
        p.error("requests and concurrency must be positive")
    report = asyncio.run(measure(a.base_url, a.requests, a.concurrency))
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
