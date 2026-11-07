"""Real PostgreSQL integration, enabled by a disposable TEST_DATABASE_URL (also wired in CI)."""

import os
import uuid

import pytest
from eventloom.matching import Matcher
from eventloom.models import Listing
from eventloom.store import Store
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def test_postgres_transactional_upsert():
    uri = os.getenv("TEST_DATABASE_URL")
    if not uri:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = "test_" + uuid.uuid4().hex
    engine = create_engine(uri)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = make_url(uri).update_query_dict({"options": f"-csearch_path={schema}"})
    store = None
    try:
        store = Store(url)
        e = dict(
            id="pg-test",
            title="Velvet Echoes",
            venue="Harbor Arena",
            city="Seattle",
            starts_at="2027-01-01T21:00:00Z",
            category="music",
            min_price_cents=4000,
        )
        store.seed_events([e])
        listing = Listing(
            provider="alpha",
            provider_id="1",
            title=e["title"],
            venue=e["venue"],
            city=e["city"],
            starts_at=e["starts_at"],
            updated_at="2026-12-01T00:00:00Z",
            price_cents=4000,
            quantity=3,
        )
        d = Matcher([e]).match(listing.record())
        assert store.write(listing, d)["applied"]
        assert not store.write(listing, d)["applied"]
        newer = listing.model_copy(
            update={
                "updated_at": listing.updated_at.replace(day=2),
                "price_cents": 3500,
            }
        )
        assert store.write(newer, d)["applied"]
        assert not store.write(listing, d)["applied"]
        assert store.offers("pg-test")[0]["price_cents"] == 3500
        assert store.inventory()["pg-test"]["quantity"] == 3
    finally:
        if store:
            store.close()
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
