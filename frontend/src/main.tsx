import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  Search,
  MapPin,
  Heart,
  X,
  SlidersHorizontal,
  Sparkles,
  Check,
  Music2,
  Trophy,
  Mic2,
  Drama,
  ChevronLeft,
  ChevronRight,
  Layers,
  LoaderCircle,
} from "lucide-react";
import "./styles.css";

type Event = {
  id: string;
  title: string;
  venue: string;
  city: string;
  starts_at: string;
  category: string;
  min_price_cents: number | null;
  listing_count: number;
};
type Offer = {
  provider: string;
  price_cents: number;
  quantity: number;
  updated_at: string;
};
type Match = {
  event_id: string | null;
  decision: string;
  reason: string;
  candidate_count: number;
  threshold: number;
  margin: number;
  candidates: {
    event_id: string;
    title: string;
    score: number;
    title_similarity: number;
    venue_similarity: number;
    time_delta_minutes: number;
  }[];
};
const categories = [
  { key: "", name: "All events", icon: Layers },
  { key: "music", name: "Music", icon: Music2 },
  { key: "sports", name: "Sports", icon: Trophy },
  { key: "comedy", name: "Comedy", icon: Mic2 },
  { key: "theater", name: "Theater", icon: Drama },
];
const money = (c: number | null) =>
  c === null
    ? "Unavailable"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(c / 100);
const when = (d: string) =>
  new Date(d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) throw new Error(`Request failed (${r.status}). Please try again.`);
  return r.json();
}
function loadSaved(): Event[] {
  try {
    const a = JSON.parse(localStorage.getItem("eventloom-saved") || "[]");
    return Array.isArray(a)
      ? a.filter(
          (e) => e && typeof e.id === "string" && typeof e.title === "string",
        )
      : [];
  } catch {
    return [];
  }
}
function App() {
  const [q, setQ] = useState(""),
    [query, setQuery] = useState(""),
    [city, setCity] = useState(""),
    [category, setCategory] = useState(""),
    [budget, setBudget] = useState(""),
    [dateFrom, setDateFrom] = useState(""),
    [dateTo, setDateTo] = useState(""),
    [sort, setSort] = useState("relevance"),
    [page, setPage] = useState(1);
  const [events, setEvents] = useState<Event[]>([]),
    [total, setTotal] = useState(0),
    [busy, setBusy] = useState(true),
    [error, setError] = useState("");
  const [stats, setStats] = useState<{
    events: number;
    cities: string[];
    listings: Record<string, number>;
  } | null>(null);
  const [saved, setSaved] = useState<Event[]>(loadSaved),
    [savedView, setSavedView] = useState(false),
    [filters, setFilters] = useState(false);
  const [selected, setSelected] = useState<Event | null>(null),
    [offers, setOffers] = useState<Offer[]>([]),
    [offerError, setOfferError] = useState(""),
    [offerBusy, setOfferBusy] = useState(false);
  const detailRef = useRef<HTMLDialogElement>(null),
    labRef = useRef<HTMLDialogElement>(null);
  const [labEvent, setLabEvent] = useState<Event | null>(null),
    [labTitle, setLabTitle] = useState(""),
    [match, setMatch] = useState<Match | null>(null),
    [matchBusy, setMatchBusy] = useState(false),
    [matchError, setMatchError] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    api<typeof stats>("/api/stats")
      .then(setStats)
      .catch(() => {});
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    setBusy(true);
    setError("");
    const p = new URLSearchParams({
      q: query,
      city,
      category,
      page: String(page),
      size: "12",
      sort,
    });
    if (budget) p.set("max_price", String(Number(budget) * 100));
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    api<{ items: Event[]; total: number }>("/api/events?" + p, {
      signal: ctrl.signal,
    })
      .then((r) => {
        setEvents(r.items);
        setTotal(r.total);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setBusy(false);
      });
    return () => ctrl.abort();
  }, [query, city, category, budget, dateFrom, dateTo, page, sort]);
  useEffect(() => {
    try {
      localStorage.setItem("eventloom-saved", JSON.stringify(saved));
    } catch {
      /* Browsing still works when storage is unavailable. */
    }
  }, [saved]);
  useEffect(() => {
    if (!selected) return;
    const ctrl = new AbortController();
    setOfferBusy(true);
    setOfferError("");
    setOffers([]);
    api<{ offers: Offer[] }>("/api/events/" + selected.id, {
      signal: ctrl.signal,
    })
      .then((r) => setOffers(r.offers))
      .catch((e) => {
        if (e.name !== "AbortError") setOfferError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setOfferBusy(false);
      });
    return () => ctrl.abort();
  }, [selected]);
  const toggle = (e: Event) =>
    setSaved((s) =>
      s.some((x) => x.id === e.id) ? s.filter((x) => x.id !== e.id) : [...s, e],
    );
  const open = (e: Event) => {
    setSelected(e);
    detailRef.current?.showModal();
  };
  const openLab = (e?: Event) => {
    const source = e || events[0] || saved[0];
    if (!source) return;
    setLabEvent(source);
    setLabTitle("Tickets: " + source.title.toUpperCase() + " — Live Tour");
    setMatch(null);
    setMatchError("");
    labRef.current?.showModal();
  };
  const runMatch = async () => {
    if (!labEvent) return;
    setMatchBusy(true);
    setMatchError("");
    try {
      const r = await api<Match>("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "playground",
          provider_id: "preview",
          title: labTitle,
          venue: labEvent.venue,
          city: labEvent.city,
          starts_at: labEvent.starts_at,
          updated_at: new Date().toISOString(),
          price_cents: 5000,
          quantity: 2,
          category: labEvent.category,
        }),
      });
      setMatch(r);
    } catch (e) {
      setMatchError((e as Error).message);
    } finally {
      setMatchBusy(false);
    }
  };
  const visible = savedView ? saved : events;
  return (
    <>
      <a className="skip" href="#results">
        Skip to events
      </a>
      <div className="site-shell">
        <header>
          <a href="/" className="brand" aria-label="EventLoom home">
            <span className="brand-symbol">
              e<span>✳</span>
            </span>
            eventloom<span className="brand-dot">.</span>
          </a>
          <nav aria-label="Main navigation">
            <button
              className={!savedView ? "active" : ""}
              onClick={() => setSavedView(false)}
            >
              Discover
            </button>
            <button
              className={savedView ? "active" : ""}
              onClick={() => setSavedView(true)}
            >
              Saved <span className="nav-count">{saved.length}</span>
            </button>
          </nav>
          <button
            className="lab-link"
            onClick={() => openLab()}
            disabled={!events.length && !saved.length}
          >
            Matching lab <ArrowUpRight size={16} />
          </button>
        </header>
        <main>
          <section className="hero">
            <div>
              <p className="eyebrow">
                <span className="pulse" /> GOOD TIMES, FOUND HERE
              </p>
              <h1>
                Your next
                <br />
                <span>had-to-be-there.</span>
              </h1>
              <p className="hero-copy">
                Small rooms. Big nights. Something unexpected.
                <br />
                Find a live experience worth stepping out for.
              </p>
              <div className="hero-foot">
                <span className="mini-mark">✳</span>
                <span>
                  One event. Every source.
                  <br />
                  <strong>A clearer way to discover.</strong>
                </span>
              </div>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orb orb-one" />
              <div className="orb orb-two" />
              <div className="orbit" />
              <span className="art-star">✳</span>
              <div className="ticket">
                <span>THE NEXT GREAT NIGHT</span>
                <div className="ticket-line" />
                <strong>BE THERE.</strong>
                <div className="ticket-bottom">
                  <span>ADMIT YOURSELF</span>
                  <span>↗</span>
                </div>
                <div className="barcode" />
              </div>
              <div className="art-caption">LESS SCROLLING. MORE LIVING. ↗</div>
            </div>
          </section>
          <div className="demo-banner">
            <span className="demo-dot" />
            <span>
              <strong>Engineering demo</strong> · All events, availability, and
              prices are synthetic.
            </span>
            <button
              onClick={() => openLab()}
              disabled={!events.length && !saved.length}
            >
              See how matching works <ArrowRight size={14} />
            </button>
          </div>
          {!savedView && (
            <section
              className="search-section"
              aria-label="Search and filter events"
            >
              <div className="searchbar">
                <Search size={21} />
                <input
                  aria-label="Search events"
                  placeholder="Artists, teams, venues… typos welcome"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
                {q && (
                  <button aria-label="Clear search" onClick={() => setQ("")}>
                    <X size={16} />
                  </button>
                )}
                <span className="divider" />
                <MapPin size={18} />
                <select
                  aria-label="City"
                  value={city}
                  onChange={(e) => {
                    setCity(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Everywhere</option>
                  {stats?.cities.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <button
                  className={"filter-button " + (filters ? "selected" : "")}
                  onClick={() => setFilters(!filters)}
                  aria-expanded={filters}
                >
                  <SlidersHorizontal size={18} />
                  <span>Filters</span>
                </button>
              </div>
              {filters && (
                <div className="extra-filters">
                  <label>
                    Maximum price ($)
                    <input
                      type="number"
                      min="0"
                      value={budget}
                      onChange={(e) => {
                        setBudget(e.target.value);
                        setPage(1);
                      }}
                      placeholder="Any price"
                    />
                  </label>
                  <label>
                    From (UTC)
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => {
                        setDateFrom(e.target.value);
                        setPage(1);
                      }}
                    />
                  </label>
                  <label>
                    To (UTC)
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => {
                        setDateTo(e.target.value);
                        setPage(1);
                      }}
                    />
                  </label>
                  <button
                    onClick={() => {
                      setBudget("");
                      setDateFrom("");
                      setDateTo("");
                      setPage(1);
                    }}
                  >
                    Reset filters
                  </button>
                </div>
              )}
              <div className="categories">
                {categories.map(({ key, name, icon: Icon }) => (
                  <button
                    key={key}
                    aria-pressed={category === key}
                    className={category === key ? "chosen" : ""}
                    onClick={() => {
                      setCategory(key);
                      setPage(1);
                    }}
                  >
                    <Icon size={16} />
                    {name}
                  </button>
                ))}
              </div>
            </section>
          )}
          <section
            id="results"
            className="results"
            aria-busy={!savedView && busy}
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">
                  {savedView
                    ? "YOUR PERSONAL SHORTLIST"
                    : "MAKE A LITTLE ROOM FOR LIVE"}
                </p>
                <h2>
                  {savedView
                    ? "Keep the good ones."
                    : query
                      ? `Results for “${query}”`
                      : "Find your kind of night."}
                </h2>
              </div>
              <div className="result-tools">
                <span aria-live="polite">
                  {(savedView ? saved.length : total).toLocaleString()} events
                </span>
                {!savedView && (
                  <select
                    aria-label="Sort events"
                    value={sort}
                    onChange={(e) => {
                      setSort(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="relevance">Recommended</option>
                    <option value="price">Price: low to high</option>
                  </select>
                )}
              </div>
            </div>
            {!savedView && error ? (
              <div role="alert" className="empty">
                {error}
              </div>
            ) : !savedView && busy ? (
              <div className="loading" role="status">
                <LoaderCircle className="spin" /> Finding your next moment…
              </div>
            ) : visible.length === 0 ? (
              <div className="empty">
                <Sparkles />
                <h3>
                  {savedView
                    ? "A little empty. Full of possibility."
                    : "No events found."}
                </h3>
                <p>
                  {savedView
                    ? "Tap the heart on an event to keep it here."
                    : "Try another city, a broader search, or fewer filters."}
                </p>
              </div>
            ) : (
              <div className="event-grid">
                {visible.map((e, i) => {
                  const Icon =
                    categories.find((c) => c.key === e.category)?.icon ||
                    Music2;
                  const isSaved = saved.some((x) => x.id === e.id);
                  return (
                    <article className={"event-card " + e.category} key={e.id}>
                      <div className={"card-art art-" + (i % 4)}>
                        <span className="card-category">
                          <Icon size={12} />
                          {e.category}
                        </span>
                        <button
                          className={"save " + (isSaved ? "is-saved" : "")}
                          aria-label={`${isSaved ? "Unsave" : "Save"} ${e.title}`}
                          aria-pressed={isSaved}
                          onClick={() => toggle(e)}
                        >
                          <Heart
                            size={18}
                            fill={isSaved ? "currentColor" : "none"}
                          />
                        </button>
                        <div className="card-pattern" aria-hidden="true" />
                        <span className="art-type" aria-hidden="true">
                          {e.category === "music"
                            ? "LIVE"
                            : e.category === "sports"
                              ? "GAME"
                              : e.category === "comedy"
                                ? "HA!"
                                : "ACT"}
                        </span>
                        <div className="date-tag">
                          {new Date(e.starts_at).toLocaleDateString("en-US", {
                            month: "short",
                            timeZone: "UTC",
                          })}
                          <strong>{new Date(e.starts_at).getUTCDate()}</strong>
                        </div>
                      </div>
                      <div className="card-body">
                        <p className="event-location">
                          {e.city} <span>↗</span>
                        </p>
                        <h3>
                          <button onClick={() => open(e)}>{e.title}</button>
                        </h3>
                        <p className="venue">{e.venue}</p>
                        <div className="card-bottom">
                          <span>
                            {e.min_price_cents === null ? (
                              "No active listings"
                            ) : (
                              <>
                                From <strong>{money(e.min_price_cents)}</strong>
                              </>
                            )}
                          </span>
                          <button
                            onClick={() => open(e)}
                            aria-label={`View ${e.title}`}
                          >
                            <ArrowUpRight size={19} />
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
            {!savedView && total > 12 && (
              <div className="pagination">
                <button
                  disabled={page === 1 || busy}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft size={16} /> Previous
                </button>
                <span>
                  Page {page} of {Math.ceil(total / 12)}
                </span>
                <button
                  disabled={page * 12 >= total || busy}
                  onClick={() => setPage(page + 1)}
                >
                  Next <ChevronRight size={16} />
                </button>
              </div>
            )}
          </section>
          <section className="under-the-hood">
            <div>
              <span className="eyebrow">BUILT WITH CURIOSITY</span>
              <h2>
                Different listings.
                <br />
                The same great night.
              </h2>
              <p>
                Our matching engine connects noisy event data using names,
                venues, cities, and times. Uncertain matches stay separate for
                review.
              </p>
              <button
                className="dark-button"
                onClick={() => openLab()}
                disabled={!events.length && !saved.length}
              >
                Explore the matching lab <ArrowUpRight size={17} />
              </button>
            </div>
            <div className="data-stack">
              <div>
                <span>CATALOG</span>
                <strong>{stats ? stats.events.toLocaleString() : "—"}</strong>
                <p>Synthetic events</p>
              </div>
              <div>
                <span>RECONCILIATION</span>
                <strong>
                  {stats
                    ? Object.values(stats.listings)
                        .reduce((a, b) => a + b, 0)
                        .toLocaleString()
                    : "—"}
                </strong>
                <p>Provider observations</p>
              </div>
              <p className="stack-note">
                <Check size={14} /> Explainable decisions · Reproducible
                evaluation
              </p>
            </div>
          </section>
        </main>
        <footer>
          <span className="brand">eventloom.</span>
          <span>Made for the moments that matter.</span>
          <span>Synthetic data · Portfolio project</span>
        </footer>
      </div>
      <dialog
        ref={detailRef}
        aria-labelledby="event-dialog-title"
        onClose={() => setSelected(null)}
        className="event-dialog"
      >
        <button
          className="close"
          aria-label="Close event details"
          onClick={() => detailRef.current?.close()}
        >
          <X />
        </button>
        {selected && (
          <>
            <span className="eyebrow">
              {selected.category} · SYNTHETIC EVENT
            </span>
            <h2 id="event-dialog-title">{selected.title}</h2>
            <p>
              {selected.venue} · {selected.city}
            </p>
            <p>
              {when(selected.starts_at)} ·{" "}
              {new Date(selected.starts_at).toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                timeZone: "UTC",
              })}{" "}
              UTC
            </p>
            <h3>Compare availability</h3>
            {offerBusy ? (
              <p role="status">Loading offers…</p>
            ) : offerError ? (
              <p role="alert">{offerError}</p>
            ) : offers.length ? (
              offers.map((o) => (
                <div className="offer" key={o.provider}>
                  <span>
                    <strong>{o.provider.replace("_", " ")}</strong>
                    <small>{o.quantity} tickets available</small>
                  </span>
                  <strong>{money(o.price_cents)}</strong>
                </div>
              ))
            ) : (
              <p>No active listings for this event.</p>
            )}
            <p className="fine">
              Demo listings only. No ticket purchases or checkout.
            </p>
            <button className="dark-button" onClick={() => toggle(selected)}>
              <Heart size={17} />
              {saved.some((x) => x.id === selected.id)
                ? "Remove from saved"
                : "Save this event"}
            </button>
            <button
              className="text-button"
              onClick={() => {
                detailRef.current?.close();
                openLab(selected);
              }}
            >
              Inspect matching <ArrowUpRight size={15} />
            </button>
          </>
        )}
      </dialog>
      <dialog
        ref={labRef}
        aria-labelledby="lab-dialog-title"
        className="lab-dialog"
      >
        <button
          className="close"
          aria-label="Close matching lab"
          onClick={() => labRef.current?.close()}
        >
          <X />
        </button>
        <span className="eyebrow">THE ENGINE, EXPLAINED</span>
        <h2 id="lab-dialog-title">
          Same event?
          <br />
          Show your work.
        </h2>
        <p>
          Edit a provider's event title. The engine searches the catalog and
          explains whether the listing can be linked with confidence.
        </p>
        {labEvent && (
          <>
            <div className="reference">
              <small>REFERENCE EVENT</small>
              <strong>{labEvent.title}</strong>
              <span>
                {labEvent.venue} · {labEvent.city} · {when(labEvent.starts_at)}
              </span>
            </div>
            <label className="lab-label">
              Provider title
              <input
                value={labTitle}
                onChange={(e) => setLabTitle(e.target.value)}
                maxLength={250}
              />
            </label>
            <button
              className="dark-button"
              disabled={matchBusy || labTitle.length < 2}
              onClick={runMatch}
            >
              {matchBusy ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <Sparkles size={17} />
              )}
              Run matching
            </button>
            {matchError && <p role="alert">{matchError}</p>}
            {match && (
              <div className="match-result" aria-live="polite">
                <span className={"decision " + match.decision}>
                  {match.decision === "matched"
                    ? "Matched confidently"
                    : "Held for review"}
                </span>
                <p>
                  {match.candidate_count} candidates ·{" "}
                  {match.reason.replaceAll("_", " ")}
                </p>
                {match.candidates.slice(0, 1).map((c) => (
                  <div key={c.event_id}>
                    <strong>{c.title}</strong>
                    {[
                      ["Overall score", c.score],
                      ["Title similarity", c.title_similarity],
                      ["Venue similarity", c.venue_similarity],
                    ].map(([label, value]) => (
                      <div className="score-row" key={String(label)}>
                        <span>{label}</span>
                        <meter min="0" max="1" value={Number(value)} />
                        <strong>{(Number(value) * 100).toFixed(1)}%</strong>
                      </div>
                    ))}
                    <small>
                      Time difference: {c.time_delta_minutes} min · Required
                      score: {(match.threshold * 100).toFixed(0)}% · Lead over
                      runner-up: {(match.margin * 100).toFixed(1)} points
                    </small>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </dialog>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
