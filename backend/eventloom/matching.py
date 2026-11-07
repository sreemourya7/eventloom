"""Deterministic candidate blocking and explainable scoring. No gold IDs are read here."""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta

from rapidfuzz.fuzz import ratio, token_sort_ratio

CITY_ALIASES = {
    "sf": "san francisco",
    "nyc": "new york",
    "la": "los angeles",
    "sj": "san jose",
}
STOP = {"live", "presents", "tickets", "tour", "the", "at", "vs", "v", "in", "concert"}


def normalize(text: str) -> str:
    value = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )
    value = re.sub(r"\b(st\.|st)\b", "street", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def city_key(city: str) -> str:
    value = normalize(city)
    return CITY_ALIASES.get(value, value)


def title_key(title: str) -> str:
    return " ".join(sorted(t for t in normalize(title).split() if t not in STOP))


def stamp(value) -> datetime:
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )


def features(a: dict, b: dict) -> dict:
    title = token_sort_ratio(title_key(a["title"]), title_key(b["title"])) / 100
    venue = ratio(normalize(a["venue"]), normalize(b["venue"])) / 100
    delta = abs((stamp(a["starts_at"]) - stamp(b["starts_at"])).total_seconds()) / 60
    same_city = city_key(a["city"]) == city_key(b["city"])
    score = 0.60 * title + 0.25 * venue + 0.15 * max(0, 1 - delta / 120)
    # Gates protect against merging different shows at the same venue.
    if not same_city or delta > 90 or title < 0.68 or venue < 0.60:
        score = 0.0
    return {
        "score": round(score, 6),
        "title_similarity": round(title, 4),
        "venue_similarity": round(venue, 4),
        "time_delta_minutes": round(delta, 2),
        "same_city": same_city,
    }


class Matcher:
    def __init__(
        self, events: list[dict], threshold: float = 0.88, margin: float = 0.04
    ):
        self.threshold, self.margin = threshold, margin
        self.events = {e["id"]: e for e in events}
        self.blocks = defaultdict(list)
        for event in events:
            self.blocks[
                (city_key(event["city"]), stamp(event["starts_at"]).date())
            ].append(event)

    def candidates(self, listing: dict) -> list[dict]:
        date = stamp(listing["starts_at"]).date()
        # Adjacent UTC days preserve recall around midnight and offset conversion.
        return [
            e
            for shift in (-1, 0, 1)
            for e in self.blocks.get(
                (city_key(listing["city"]), date + timedelta(days=shift)), []
            )
        ]

    def match(self, listing: dict) -> dict:
        candidates = self.candidates(listing)
        ranked = sorted(
            (
                dict(event_id=e["id"], title=e["title"], **features(listing, e))
                for e in candidates
            ),
            key=lambda x: (-x["score"], x["event_id"]),
        )
        best = ranked[0] if ranked else None
        gap = (
            best["score"] - ranked[1]["score"]
            if len(ranked) > 1
            else (best["score"] if best else 0)
        )
        accepted = bool(best and best["score"] >= self.threshold and gap >= self.margin)
        return {
            "event_id": best["event_id"] if accepted else None,
            "decision": "matched" if accepted else "review",
            "reason": "confident_match"
            if accepted
            else "no_candidates"
            if not best
            else "below_threshold"
            if best["score"] < self.threshold
            else "ambiguous_candidates",
            "candidate_count": len(candidates),
            "threshold": self.threshold,
            "margin": round(gap, 6),
            "required_margin": self.margin,
            "candidates": ranked[:3],
        }
