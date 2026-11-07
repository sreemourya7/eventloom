"""SQLAlchemy persistence with transactional, version-guarded provider upserts."""

import json
from datetime import UTC

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy import event as sa_event
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import Listing

metadata = MetaData()
events_table = Table(
    "events",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("payload", Text, nullable=False),
)
listings_table = Table(
    "listings",
    metadata,
    Column("provider", String(60), primary_key=True),
    Column("provider_id", String(100), primary_key=True),
    Column("event_id", String(100), ForeignKey("events.id"), index=True),
    Column("status", String(20), nullable=False, index=True),
    Column("updated_at", String(40), nullable=False),
    Column("price_cents", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("decision", Text, nullable=False),
)


class Store:
    def __init__(self, url="sqlite:///eventloom.db"):
        self.engine = create_engine(
            url,
            **(
                {"connect_args": {"check_same_thread": False}}
                if str(url).startswith("sqlite")
                else {}
            ),
        )
        if str(url).startswith("sqlite"):

            @sa_event.listens_for(self.engine, "connect")
            def pragmas(dbapi_connection, _):
                dbapi_connection.execute("PRAGMA foreign_keys=ON")
                dbapi_connection.execute("PRAGMA journal_mode=WAL")
                dbapi_connection.execute("PRAGMA busy_timeout=5000")

        metadata.create_all(self.engine)

    def insert(self, table):
        return (sqlite_insert if self.engine.dialect.name == "sqlite" else pg_insert)(
            table
        )

    def seed_events(self, events):
        with self.engine.begin() as conn:
            if conn.scalar(select(func.count()).select_from(events_table)):
                raise ValueError(
                    "Catalog is non-empty. Use a new database to seed another fixture."
                )
            conn.execute(
                events_table.insert(),
                [{"id": e["id"], "payload": json.dumps(e)} for e in events],
            )

    def events(self):
        with self.engine.connect() as conn:
            return [
                json.loads(row[0])
                for row in conn.execute(
                    select(events_table.c.payload).order_by(events_table.c.id)
                )
            ]

    def write(self, listing: Listing, decision: dict) -> dict:
        data = dict(
            provider=listing.provider,
            provider_id=listing.provider_id,
            event_id=decision["event_id"],
            status=decision["decision"],
            updated_at=listing.updated_at.astimezone(UTC).isoformat(
                timespec="microseconds"
            ),
            price_cents=listing.price_cents,
            quantity=listing.quantity,
            payload=json.dumps(listing.record()),
            decision=json.dumps(decision),
        )
        stmt = self.insert(listings_table).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[listings_table.c.provider, listings_table.c.provider_id],
            set_={
                k: getattr(stmt.excluded, k)
                for k in data
                if k not in ("provider", "provider_id")
            },
            where=stmt.excluded.updated_at > listings_table.c.updated_at,
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            return {
                "applied": result.rowcount == 1,
                "provider": listing.provider,
                "provider_id": listing.provider_id,
                "decision": decision,
            }

    def inventory(self):
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(
                    listings_table.c.event_id,
                    func.min(listings_table.c.price_cents).label("min_price_cents"),
                    func.count().label("listing_count"),
                    func.sum(listings_table.c.quantity).label("quantity"),
                )
                .where(
                    listings_table.c.status == "matched", listings_table.c.quantity > 0
                )
                .group_by(listings_table.c.event_id)
            )
            return {
                r.event_id: dict(
                    min_price_cents=r.min_price_cents,
                    listing_count=r.listing_count,
                    quantity=r.quantity,
                )
                for r in rows
            }

    def offers(self, event_id):
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(listings_table.c.payload)
                .where(
                    listings_table.c.event_id == event_id,
                    listings_table.c.status == "matched",
                    listings_table.c.quantity > 0,
                )
                .order_by(listings_table.c.price_cents)
            )
            return [json.loads(r[0]) for r in rows]

    def review(self, limit=50):
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(listings_table)
                .where(listings_table.c.status == "review")
                .order_by(
                    listings_table.c.updated_at.desc(), listings_table.c.provider_id
                )
                .limit(limit)
            )
            return [
                dict(listing=json.loads(r.payload), decision=json.loads(r.decision))
                for r in rows
            ]

    def counts(self):
        with self.engine.connect() as conn:
            return {
                str(status): count
                for status, count in conn.execute(
                    select(listings_table.c.status, func.count()).group_by(
                        listings_table.c.status
                    )
                )
            }

    def close(self):
        self.engine.dispose()
