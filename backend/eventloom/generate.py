"""Seeded synthetic data. Fabricated events/prices, never actual ticket inventory."""

import argparse
import hashlib
import json
import random
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

CITIES = [
    "San Francisco",
    "San Jose",
    "Los Angeles",
    "New York",
    "Chicago",
    "Austin",
    "Seattle",
    "Boston",
]
ADJECTIVES = [
    "Velvet",
    "Neon",
    "Midnight",
    "Silver",
    "Golden",
    "Electric",
    "Crimson",
    "Wild",
    "Paper",
    "Lunar",
    "Blue",
    "Quiet",
]
NOUNS = [
    "Echoes",
    "Hearts",
    "Rivers",
    "Atlas",
    "Parade",
    "Satellites",
    "Waves",
    "Orchard",
    "Ghosts",
    "Skylines",
]
VENUES = ["Harbor Arena", "Union Theater", "Riverside Hall", "Civic Pavilion"]
BASE = datetime(2027, 1, 1, tzinfo=UTC)


def split_for(event_id: str) -> str:
    # Whole event groups, including all their source variants, share one split.
    n = int(hashlib.sha256(event_id.encode()).hexdigest()[:8], 16) % 10
    return "dev" if n < 2 else "test"


def generate(count: int = 12000, seed: int = 42):
    rng = random.Random(seed)
    slots = [
        (city, venue, day, hour)
        for city in CITIES
        for venue in VENUES
        for day in range(240)
        for hour in (15, 18, 21)
    ]
    if not 1 <= count <= len(slots):
        raise ValueError(f"events must be between 1 and {len(slots)}")
    rng.shuffle(slots)
    events, observations = [], []
    for i, (city, venue, day, hour) in enumerate(slots[:count]):
        category = rng.choices(["music", "sports", "comedy", "theater"], [6, 2, 1, 1])[
            0
        ]
        title = f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}"
        if category == "sports":
            title = f"{rng.choice(['Falcons', 'Comets', 'Wolves', 'Tigers'])} vs {rng.choice(['Bears', 'Kings', 'Stars', 'Foxes'])}"
        elif category == "comedy":
            title += " Comedy"
        elif category == "theater":
            title += " Musical"
        event_id = f"evt_{i:06d}"
        date = BASE + timedelta(days=day, hours=hour)
        price = rng.randrange(2000, 18000, 100)
        event = dict(
            id=event_id,
            title=title,
            venue=venue,
            city=city,
            starts_at=date.isoformat(),
            category=category,
            min_price_cents=price,
            split=split_for(event_id),
        )
        events.append(event)
        for source in range(3):
            mode = rng.choices(
                ["clean", "decorated", "typo", "offset", "missing", "drift"],
                [25, 25, 20, 15, 10, 5],
            )[0]
            name, hall, town, when = title, venue, city, date
            if mode == "decorated":
                name = f"Tickets: {title.upper()} — Live Tour"
                if " vs " in title:
                    home, away = title.split(" vs ")
                    name = f"{away} @ {home}"
            elif mode == "typo":
                p = rng.randrange(1, len(name) - 1)
                name = name[:p] + name[p + 1] + name[p] + name[p + 2 :]
                hall = hall.replace("Theater", "Theatre")
            elif mode == "offset":
                when = date.astimezone(timezone(timedelta(hours=-8)))
                town = {
                    "San Francisco": "SF",
                    "New York": "NYC",
                    "Los Angeles": "LA",
                    "San Jose": "SJ",
                }.get(city, city)
            elif mode == "missing":
                name = name.split()[
                    0
                ]  # intentionally insufficient evidence; should often abstain
            elif mode == "drift":
                when += timedelta(minutes=rng.choice([-120, -45, 45, 120]))
            obs = dict(
                provider=f"feed_{source}",
                provider_id=f"listing_{i:06d}",
                title=name,
                venue=hall,
                city=town,
                starts_at=when.isoformat(),
                updated_at=(BASE - timedelta(days=1)).isoformat(),
                category=category,
                price_cents=max(500, price + rng.randrange(-500, 1000, 100)),
                quantity=rng.randint(0, 8),
            )
            observations.append(
                dict(
                    listing=obs,
                    gold_event_id=event_id,
                    split=event["split"],
                    noise=mode,
                )
            )
        # Open-set negatives: plausible title and venue, different date or performer.
        if i % 10 == 0:
            unknown = {
                **obs,
                "provider": "unseen",
                "provider_id": f"unknown_{i}",
                "title": f"Unannounced Guest {i}",
                "quantity": 2,
            }
            observations.append(
                dict(
                    listing=unknown,
                    gold_event_id=None,
                    split=event["split"],
                    noise="unknown",
                )
            )
    return events, observations


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=int, default=12000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="data")
    args = p.parse_args()
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    events, observations = generate(args.events, args.seed)
    (target / "events.json").write_text(json.dumps(events), encoding="utf-8")
    with (target / "observations.jsonl").open("w", encoding="utf-8") as f:
        for row in observations:
            f.write(json.dumps(row) + "\n")
    (target / "manifest.json").write_text(
        json.dumps(
            dict(
                seed=args.seed,
                events=len(events),
                observations=len(observations),
                synthetic=True,
                split="SHA256(event_id) mod 10; 0-1 dev, 2-9 test",
            ),
            indent=2,
        )
    )
    print(
        f"Generated {len(events):,} synthetic events and {len(observations):,} observations in {target}"
    )


if __name__ == "__main__":
    main()
