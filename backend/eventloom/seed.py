import argparse
import json
import os
from pathlib import Path

from .matching import Matcher
from .models import Listing
from .store import Store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    p.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL", "sqlite:///eventloom.db")
    )
    p.add_argument("--config", default="benchmarks/matcher_config.json")
    args = p.parse_args()
    events = json.loads((Path(args.data) / "events.json").read_text())
    config = (
        json.loads(Path(args.config).read_text()) if Path(args.config).exists() else {}
    )
    matcher = Matcher(events, config.get("threshold", 0.88), config.get("margin", 0.04))
    store = Store(args.database_url)
    store.seed_events(events)
    # Fixture import uses the same matcher and upsert path as the API. No gold labels are used.
    with (Path(args.data) / "observations.jsonl").open() as f:
        for line in f:
            listing = Listing(**json.loads(line)["listing"])
            store.write(listing, matcher.match(listing.record()))
    print(json.dumps({"events": len(events), "listings": store.counts()}, indent=2))
    store.close()


if __name__ == "__main__":
    main()
