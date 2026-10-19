"""
Remembers every job ad we've ever seen, per company, in data/companies/<id>.json.

Only real events change the file (new ad, ad gone, ad re-dated), so the git history
stays small and readable: one commit per night shows exactly what moved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WS = re.compile(r"\s+")
NOISE = re.compile(r"[\(\[].*?[\)\]]|\b(m/w/d|f/m/d|f/m/x|w/m/d|m/f/d|all genders)\b", re.IGNORECASE)


def fingerprint(title: str, location: str) -> str:
    """Same role in the same place, even if they re-posted it under a new id."""
    t = NOISE.sub("", title.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return WS.sub(" ", f"{t} @ {location.lower()}").strip()


def path_for(root: Path, company_id: str) -> Path:
    return root / "data" / "companies" / f"{company_id}.json"


def load(root: Path, company_id: str) -> dict:
    p = path_for(root, company_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"jobs": {}, "history": []}


def save(root: Path, company_id: str, state: dict) -> None:
    p = path_for(root, company_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def update(state: dict, live: list[dict], now: str, evergreen_fn=None) -> dict:
    """Merge tonight's live ads into what we remember. Returns a small summary of what moved."""
    jobs = state.setdefault("jobs", {})
    live_ids = set()
    moved = {"new": 0, "closed": 0, "reopened": 0, "redated": 0}

    for j in live:
        jid = j["id"]
        live_ids.add(jid)
        rec = jobs.get(jid)
        evergreen = bool(evergreen_fn(j["title"], j.get("text", ""))) if evergreen_fn else False
        if rec is None:
            jobs[jid] = {
                "title": j["title"], "location": j["location"], "department": j.get("department", ""),
                "url": j["url"], "posted_at": j["posted_at"], "posted_history": [j["posted_at"]] if j["posted_at"] else [],
                "first_seen": now, "closed_at": None, "reopened": 0,
                "fp": fingerprint(j["title"], j["location"]), "evergreen": evergreen,
            }
            moved["new"] += 1
            continue
        if rec.get("closed_at"):
            rec["closed_at"] = None
            rec["reopened"] = rec.get("reopened", 0) + 1
            moved["reopened"] += 1
        # The board re-dated an ad we already know: it now claims to be newer than it is.
        if j["posted_at"] and rec.get("posted_at") and j["posted_at"] > rec["posted_at"]:
            rec.setdefault("posted_history", []).append(j["posted_at"])
            rec["posted_at"] = j["posted_at"]
            moved["redated"] += 1
        elif j["posted_at"] and not rec.get("posted_at"):
            rec["posted_at"] = j["posted_at"]
        for key in ("title", "location", "url"):
            if j.get(key) and j[key] != rec.get(key):
                rec[key] = j[key]
        rec["fp"] = fingerprint(rec["title"], rec["location"])
        if evergreen and not rec.get("evergreen"):
            rec["evergreen"] = True

    for jid, rec in jobs.items():
        if not rec.get("closed_at") and jid not in live_ids:
            rec["closed_at"] = now
            moved["closed"] += 1

    day = now[:10]
    hist = state.setdefault("history", [])
    if hist and hist[-1]["date"] == day:
        hist[-1]["open"] = len(live_ids)
    else:
        hist.append({"date": day, "open": len(live_ids)})
    return moved
