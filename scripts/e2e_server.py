"""Use the project's virtualenv when Playwright starts a local test server."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.exists():
    python = Path(sys.executable)
os.chdir(root)
subprocess.run(
    [
        str(python),
        "-m",
        "uvicorn",
        "eventloom.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8766",
        "--no-access-log",
    ],
    check=True,
)
