"""Trigram retrieval with a bounded query-ranking cache over an immutable catalog.

Only text relevance is cached. Current prices, quantities, filters, and pagination
are evaluated on every request, so inventory updates cannot stale a price filter.
"""

from collections import defaultdict
from functools import lru_cache

from rapidfuzz.fuzz import WRatio, token_sort_ratio

from .matching import city_key, normalize


def trigrams(text: str) -> set[str]:
    text = normalize(text)
    return {text[i : i + 3] for i in range(max(0, len(text) - 2))}


def relevance(query, title, venue, document):
    return max(
        token_sort_ratio(query, title),
        0.95 * WRatio(query, title),
        0.90 * WRatio(query, venue),
        0.85 * WRatio(query, document),
    )


class SearchIndex:
    def __init__(self, events: list[dict]):
        self.events = {e["id"]: e for e in events}
        self.docs, self.fields = {}, {}
        self.postings, self.tokens = defaultdict(set), defaultdict(set)
        for event in events:
            key = event["id"]
            doc = normalize(f"{event['title']} {event['venue']} {event['city']}")
            self.docs[key] = doc
            self.fields[key] = (normalize(event["title"]), normalize(event["venue"]))
            for gram in trigrams(doc):
                self.postings[gram].add(key)
            for token in doc.split():
                self.tokens[token].add(key)
        self.rank = lru_cache(maxsize=128)(self._rank)

    def _rank(self, normalized):
        if not normalized:
            return tuple((key, 100.0) for key in self.events), len(self.events)
        grams = trigrams(normalized)
        counts = defaultdict(int)
        for gram in grams:
            for key in self.postings.get(gram, ()):
                counts[key] += 1
        # Do not truncate globally before city/date/price filters are applied.
        min_hits = max(1, int(len(grams) * 0.20))
        ids = {key for key, count in counts.items() if count >= min_hits}
        if len(normalized) < 3:
            ids = {
                key
                for token, keys in self.tokens.items()
                if token.startswith(normalized)
                for key in keys
            }
        ranked = []
        for key in ids:
            score = relevance(normalized, *self.fields[key], self.docs[key])
            if score >= 58:
                ranked.append((key, round(score, 2)))
        return tuple(ranked), len(ids)

    def search(
        self,
        q="",
        city="",
        category="",
        max_price=None,
        date_from=None,
        date_to=None,
        page=1,
        size=12,
        sort="relevance",
        available=None,
    ) -> dict:
        ranked, examined = self.rank(normalize(q))
        rows = []
        for key, score in ranked:
            e = self.events[key]
            inventory = available.get(key) if available is not None else None
            price = (
                inventory["min_price_cents"]
                if inventory
                else (None if available is not None else e["min_price_cents"])
            )
            if city and city_key(e["city"]) != city_key(city):
                continue
            if category and category != e["category"]:
                continue
            day = e["starts_at"][:10]
            if (date_from and day < str(date_from)) or (date_to and day > str(date_to)):
                continue
            if max_price is not None and (price is None or price > max_price):
                continue
            rows.append(
                {
                    **e,
                    "min_price_cents": price,
                    "listing_count": inventory["listing_count"] if inventory else 0,
                    "search_score": score,
                }
            )
        rows.sort(
            key=(
                lambda e: (
                    e["min_price_cents"] is None,
                    e["min_price_cents"] or 0,
                    e["id"],
                )
            )
            if sort == "price"
            else lambda e: (-e["search_score"], e["starts_at"], e["id"])
        )
        start = (page - 1) * size
        return {
            "items": rows[start : start + size],
            "total": len(rows),
            "page": page,
            "size": size,
            "candidates_examined": examined,
        }
