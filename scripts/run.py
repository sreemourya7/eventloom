"""Cross-platform first-run launcher. Run with Python 3.11+ from any directory."""

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--no-serve",
        action="store_true",
        help="Install and seed without starting the server",
    )
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required")
    os.chdir(ROOT)
    env = ROOT / ".venv"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    fresh = not python.exists()
    if fresh:
        print("Creating project environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(env)
    if fresh or not (env / ".eventloom-ready").exists():
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", "requirements.lock"], check=True
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "-e", "backend"],
            check=True,
        )
        (env / ".eventloom-ready").write_text("1")
    subprocess.run([str(python), "scripts/initialize.py"], check=True)
    if not a.no_serve:
        print(f"Open http://localhost:{a.port} (Ctrl+C to stop)", flush=True)
        try:
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "eventloom.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(a.port),
                ],
                check=True,
            )
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
