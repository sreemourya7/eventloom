import json
import os
import secrets
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .matching import Matcher
from .models import Listing
from .search import SearchIndex
from .store import Store


class InventoryView:
    """Single-process read model; writes invalidate it synchronously."""

    def __init__(self, store):
        self.store, self.lock, self.cached = store, threading.RLock(), None

    def get(self):
        with self.lock:
            if self.cached is None:
                self.cached = self.store.inventory()
            return self.cached

    def write(self, listing, decision):
        with self.lock:
            result = self.store.write(listing, decision)
            if result["applied"]:
                self.cached = None
            return result


def create_app(database_url=None, config_path=None, frontend_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        store = Store(
            database_url or os.getenv("DATABASE_URL", "sqlite:///eventloom.db")
        )
        app.state.store = store
        events = store.events()
        path = Path(
            config_path or os.getenv("MATCHER_CONFIG", "benchmarks/matcher_config.json")
        )
        config = json.loads(path.read_text()) if path.exists() else {}
        app.state.matcher = Matcher(
            events, config.get("threshold", 0.88), config.get("margin", 0.04)
        )
        app.state.search = SearchIndex(events)
        app.state.inventory = InventoryView(store)
        app.state.latencies = deque(maxlen=10000)
        yield
        store.close()

    app = FastAPI(
        title="EventLoom",
        version="1.0.0",
        lifespan=lifespan,
        description="Synthetic event catalog; explainable entity resolution and typo-tolerant search.",
    )

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["Server-Timing"] = f"app;dur={ms:.3f}"
        if hasattr(app.state, "latencies"):
            app.state.latencies.append(ms)
        return response

    def admin(x_admin_token: str | None = Header(default=None)):
        expected = os.getenv("ADMIN_TOKEN", "")
        if not expected:
            raise HTTPException(503, "Ingestion disabled: configure ADMIN_TOKEN")
        if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
            raise HTTPException(401, "Invalid admin token")

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "catalog_events": len(app.state.matcher.events),
            "synthetic": True,
        }

    @app.get("/api/events")
    def search(
        q: str = Query("", max_length=200),
        city: str = Query("", max_length=80),
        category: Literal["", "music", "sports", "comedy", "theater"] = "",
        max_price: int | None = Query(None, ge=0),
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = Query(1, ge=1, le=100000),
        size: int = Query(12, ge=1, le=100),
        sort: Literal["relevance", "price"] = "relevance",
    ):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must precede date_to")
        return app.state.search.search(
            q,
            city,
            category,
            max_price,
            date_from,
            date_to,
            page,
            size,
            sort,
            app.state.inventory.get(),
        )

    @app.get("/api/events/{event_id}")
    def detail(event_id: str):
        event = app.state.matcher.events.get(event_id)
        if event is None:
            raise HTTPException(404, "Event not found")
        return {**event, "offers": app.state.store.offers(event_id), "synthetic": True}

    @app.post("/api/match")
    def match(listing: Listing):
        return app.state.matcher.match(listing.record())

    @app.post("/api/ingest", dependencies=[Depends(admin)])
    def ingest(listing: Listing):
        decision = app.state.matcher.match(listing.record())
        return app.state.inventory.write(listing, decision)

    @app.get("/api/review", dependencies=[Depends(admin)])
    def review(limit: int = Query(20, ge=1, le=100)):
        return {"items": app.state.store.review(limit)}

    @app.get("/api/stats")
    def stats():
        inventory = app.state.inventory.get()
        return {
            "events": len(app.state.matcher.events),
            "cities": sorted({e["city"] for e in app.state.matcher.events.values()}),
            "listings": app.state.store.counts(),
            "available_events": len(inventory),
            "synthetic": True,
        }

    @app.get("/api/metrics", dependencies=[Depends(admin)])
    def metrics():
        samples = sorted(app.state.latencies)
        return {
            "window": len(samples),
            "app_p95_ms": samples[min(len(samples) - 1, int(len(samples) * 0.95))]
            if samples
            else None,
            "note": "Bounded in-process middleware timings, not a distributed telemetry service",
        }

    root = Path(frontend_dir or os.getenv("FRONTEND_DIR", "frontend/dist"))
    if root.exists():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(root / "index.html")

    return app


app = create_app()
