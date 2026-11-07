"""Initialize an empty local/deployment database before starting the API."""

import os
import subprocess
import sys
from pathlib import Path

from eventloom.store import Store

if not Path("data/events.json").exists():
    subprocess.run([sys.executable, "-m", "eventloom.generate"], check=True)
store = Store(os.getenv("DATABASE_URL", "sqlite:///eventloom.db"))
exists = bool(store.events())
store.close()
if not exists:
    print(
        "Seeding 12,000 synthetic events and reconciling provider feeds. This takes about a minute…",
        flush=True,
    )
    subprocess.run([sys.executable, "-m", "eventloom.seed"], check=True)
else:
    print("Existing catalog found; preserving data.", flush=True)
