"""Start a temporary API process and measure it over real localhost HTTP."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--requests", type=int, default=800)
    p.add_argument("--concurrency", type=int, default=8)
    a = p.parse_args()
    with Path("benchmarks/server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "eventloom.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(a.port),
                "--no-access-log",
            ],
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("API exited; inspect benchmarks/server.log")
                    try:
                        if (
                            client.get(
                                f"http://127.0.0.1:{a.port}/api/health"
                            ).status_code
                            == 200
                        ):
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("API did not become healthy")
            subprocess.run(
                [
                    sys.executable,
                    "scripts/load_test.py",
                    "--base-url",
                    f"http://127.0.0.1:{a.port}",
                    "--requests",
                    str(a.requests),
                    "--concurrency",
                    str(a.concurrency),
                ],
                check=True,
            )
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
