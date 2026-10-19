"""
Ghost signals. We never claim an ad is fake — we show facts that make people side-eye it:

  age          how long the ad has really been up (oldest date we can prove)
  reposted     the same role in the same place closed and came back under a new ad
  redated      the board bumped the date so an old ad looks fresh
  evergreen    the ad says it's for a "talent pool", "future opportunities", etc.

Ghost score 0–5 combines them. Labels: 0–1 looks active, 2 stale, 3 suspicious, 4–5 ghost.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from statistics import median

EVERGREEN_TITLE = re.compile(
    r"talent (pool|community|network)|future (opportunit|role|opening)|general application|open application|"
    r"spontaneous application|expression of interest|initiativbewerbung|blind(bewerbung)?|"
    r"always (hiring|looking)|join our talent|pipeline (role|requisition|opening)|evergreen|interest form",
    re.IGNORECASE,
)
EVERGREEN_TEXT = re.compile(
    r"(this (is|role is) (an )?(evergreen|pipeline) (role|requisition|posting|position))|"
    r"(not (an )?(active|current) (opening|vacancy|role))|"
    r"(for (our )?(talent pool|future (opportunities|openings|roles)))|"
    r"(no (immediate|current) (opening|vacancy))",
    re.IGNORECASE,
)

LABELS = {0: "active", 1: "active", 2: "stale", 3: "suspicious", 4: "ghost", 5: "ghost"}


def is_evergreen(title: str, text: str = "") -> bool:
    return bool(EVERGREEN_TITLE.search(title) or (text and EVERGREEN_TEXT.search(text)))


def _dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def analyze(state: dict, now: str) -> list[dict]:
    """Every open ad with its ghost signals and score."""
    t_now = _dt(now)
    jobs = state.get("jobs", {})
    closed_by_fp: dict[str, list[dict]] = {}
    for rec in jobs.values():
        if rec.get("closed_at"):
            closed_by_fp.setdefault(rec["fp"], []).append(rec)

    out = []
    for jid, rec in jobs.items():
        if rec.get("closed_at"):
            continue
        first_seen = _dt(rec["first_seen"])
        dates = [d for d in (_dt(p) for p in rec.get("posted_history", [])) if d] + [first_seen]
        # Earlier ads for the same role+place that closed before this one appeared = reposts
        prior = [p for p in closed_by_fp.get(rec["fp"], []) if _dt(p["closed_at"]) <= first_seen]
        for p in prior:
            dates += [d for d in (_dt(x) for x in p.get("posted_history", [])) if d] + [_dt(p["first_seen"])]
        since = min(dates)
        age = max(0, (t_now - since).days)
        reposts = len(prior) + rec.get("reopened", 0)
        redated = max(0, len(rec.get("posted_history", [])) - 1)

        score = 0
        score += 3 if age >= 365 else 2 if age >= 180 else 1 if age >= 90 else 0
        score += 2 if reposts >= 3 else 1 if reposts >= 1 else 0
        score += 1 if redated else 0
        score += 2 if rec.get("evergreen") else 0
        score = min(score, 5)

        out.append({
            "id": jid, "title": rec["title"], "location": rec["location"], "department": rec.get("department", ""),
            "url": rec["url"], "since": since.date().isoformat(), "age_days": age,
            "reposts": reposts, "redated": redated, "evergreen": bool(rec.get("evergreen")),
            "score": score, "label": LABELS[score],
        })
    return sorted(out, key=lambda j: (-j["score"], -j["age_days"], j["title"]))


def company_summary(jobs: list[dict]) -> dict:
    n = len(jobs)
    if not n:
        return {"open": 0, "median_age": 0, "pct_90": 0, "pct_180": 0, "ghosts": 0, "oldest": 0, "ghost_index": 0}
    ages = [j["age_days"] for j in jobs]
    pct_90 = round(100 * sum(a >= 90 for a in ages) / n)
    pct_180 = round(100 * sum(a >= 180 for a in ages) / n)
    ghosts = sum(j["score"] >= 4 for j in jobs)
    # One number to rank boards by: how much of the board is stale, weighted toward the very old.
    ghost_index = round(0.5 * pct_90 + 0.3 * pct_180 + 20 * ghosts / n)
    return {"open": n, "median_age": int(median(ages)), "pct_90": pct_90, "pct_180": pct_180,
            "ghosts": ghosts, "oldest": max(ages), "ghost_index": min(ghost_index, 100)}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
