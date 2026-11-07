from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from eventloom.api import create_app
from eventloom.generate import generate
from eventloom.matching import Matcher
from eventloom.models import Listing
from eventloom.search import SearchIndex
from eventloom.store import Store
from fastapi.testclient import TestClient
from pydantic import ValidationError


def event(id="one", **kwargs):
    return dict(
        id=id,
        title="Velvet Echoes",
        venue="Harbor Arena",
        city="San Francisco",
        starts_at="2027-01-05T21:00:00+00:00",
        category="music",
        min_price_cents=4000,
        **kwargs,
    )


def listing(**overrides):
    data = dict(
        provider="alpha",
        provider_id="1",
        title="Tickets: VELVET ECHOES — Live Tour",
        venue="Harbor Arena",
        city="SF",
        starts_at="2027-01-05T13:00:00-08:00",
        updated_at="2027-01-01T00:00:00+00:00",
        price_cents=4000,
        quantity=2,
    )
    return Listing(**{**data, **overrides})


@pytest.fixture
def store(tmp_path):
    s = Store(f"sqlite:///{tmp_path}/test.db")
    s.seed_events([event()])
    yield s
    s.close()


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "unit-test-token")
    with TestClient(
        create_app(str(store.engine.url), frontend_dir="does-not-exist")
    ) as c:
        yield c


def test_aliases_and_timezone():
    result = Matcher([event()]).match(listing().record())
    assert result["event_id"] == "one"
    assert result["candidates"][0]["time_delta_minutes"] == 0


def test_reversed_sports_teams():
    a = {**event(), "title": "Falcons vs Bears"}
    assert (
        Matcher([a]).match(listing(title="Bears @ Falcons").record())["event_id"]
        == "one"
    )


def test_unknown_artist_abstains():
    assert (
        Matcher([event()]).match(
            listing(title="Some Completely Different Performer").record()
        )["event_id"]
        is None
    )


def test_separate_showtimes_do_not_merge():
    assert (
        Matcher([event()]).match(listing(starts_at="2027-01-05T18:00:00Z").record())[
            "event_id"
        ]
        is None
    )


def test_ambiguous_candidates_abstain():
    result = Matcher([event(), {**event(), "id": "two"}]).match(listing().record())
    assert result["reason"] == "ambiguous_candidates"


def test_midnight_candidate_block():
    a = {**event(), "starts_at": "2027-01-06T00:15:00Z"}
    result = Matcher([a], threshold=0.8).match(
        listing(starts_at="2027-01-05T23:50:00Z").record()
    )
    assert result["event_id"] == "one"


@pytest.mark.parametrize(
    "overrides",
    [
        {"starts_at": "2027-01-05T21:00:00"},
        {"price_cents": -1},
        {"quantity": -2},
        {"title": ""},
        {"category": "invalid"},
    ],
)
def test_invalid_listing(overrides):
    with pytest.raises(ValidationError):
        listing(**overrides)


def test_monotonic_inventory_and_idempotency(store):
    decision = Matcher([event()]).match(listing().record())
    assert store.write(listing(), decision)["applied"]
    assert not store.write(listing(price_cents=100), decision)["applied"]
    assert not store.write(
        listing(updated_at="2026-12-31T00:00:00Z", price_cents=1), decision
    )["applied"]
    assert store.offers("one")[0]["price_cents"] == 4000
    assert store.write(
        listing(updated_at="2027-01-02T00:00:00Z", quantity=0), decision
    )["applied"]
    assert store.offers("one") == []


def test_concurrent_versions_preserve_latest(store):
    decision = Matcher([event()]).match(listing().record())
    base = datetime(2027, 1, 1, tzinfo=UTC)

    def update(i):
        return store.write(
            listing(
                updated_at=(base + timedelta(seconds=i)).isoformat(),
                price_cents=i * 100,
            ),
            decision,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(update, [9, 1, 3, 8, 2, 7, 4, 6, 5, 0]))
    assert store.offers("one")[0]["price_cents"] == 900


def test_provider_ids_are_scoped(store):
    d = Matcher([event()]).match(listing().record())
    store.write(listing(), d)
    store.write(listing(provider="beta"), d)
    assert len(store.offers("one")) == 2


def test_review_never_enters_active_inventory(store):
    row = listing(title="Unknown Guest")
    store.write(row, Matcher([event()]).match(row.record()))
    assert store.offers("one") == []
    assert len(store.review()) == 1


def test_filters_before_pagination():
    events = [
        {**event(), "id": f"e{i}", "city": "Chicago" if i < 25 else "Seattle"}
        for i in range(30)
    ]
    result = SearchIndex(events).search(
        q="Velvt Echoes", city="Seattle", size=2, page=2
    )
    assert result["total"] == 5
    assert len(result["items"]) == 2
    assert all(e["city"] == "Seattle" for e in result["items"])


def test_no_active_inventory_does_not_advertise_seed_price():
    result = SearchIndex([event()]).search(available={})
    assert result["items"][0]["min_price_cents"] is None
    assert SearchIndex([event()]).search(max_price=10000, available={})["total"] == 0


def test_search_date_price_and_prefix():
    index = SearchIndex([event()])
    assert index.search(q="ve")["total"] == 1
    assert index.search(max_price=3999)["total"] == 0
    assert index.search(date_from="2027-01-06")["total"] == 0


def test_api_auth_validation_and_not_found(client):
    payload = listing().record()
    assert client.post("/api/ingest", json=payload).status_code == 401
    assert (
        client.post(
            "/api/ingest", json=payload, headers={"X-Admin-Token": "wrong"}
        ).status_code
        == 401
    )
    assert client.get("/api/events/missing").status_code == 404
    assert client.get("/api/events?size=9999").status_code == 422
    assert (
        client.get("/api/events?date_from=2027-02-01&date_to=2027-01-01").status_code
        == 422
    )
    assert client.get("/api/events?max_price=-1").status_code == 422


def test_api_ingestion_updates_read_model(client):
    assert client.get("/api/events").json()["items"][0]["min_price_cents"] is None
    r = client.post(
        "/api/ingest",
        json=listing().record(),
        headers={"X-Admin-Token": "unit-test-token"},
    )
    assert r.status_code == 200 and r.json()["applied"]
    assert client.get("/api/events").json()["items"][0]["min_price_cents"] == 4000
    assert (
        client.post(
            "/api/ingest",
            json=listing().record(),
            headers={"X-Admin-Token": "unit-test-token"},
        ).json()["applied"]
        is False
    )
    assert "app;dur=" in client.get("/api/health").headers["server-timing"]


def test_disabled_ingestion_without_token(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN")
    assert client.post("/api/ingest", json=listing().record()).status_code == 503


def test_generator_reproducibility_and_split_isolation():
    events, rows = generate(100)
    assert (events, rows) == generate(100)
    ids = {e["id"]: e for e in events}
    for row in rows:
        if row["gold_event_id"]:
            assert row["split"] == ids[row["gold_event_id"]]["split"]
    dev = {e["id"] for e in events if e["split"] == "dev"}
    test = {e["id"] for e in events if e["split"] == "test"}
    assert not dev & test


def test_query_cache_does_not_stale_inventory_filters():
    index = SearchIndex([event()])
    live = {"one": {"min_price_cents": 4000, "listing_count": 1}}
    assert index.search(q="Velvet", max_price=5000, available=live)["total"] == 1
    live["one"]["min_price_cents"] = 6000
    assert index.search(q="Velvet", max_price=5000, available=live)["total"] == 0
    assert index.rank.cache_info().hits == 1
