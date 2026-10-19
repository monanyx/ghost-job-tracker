"""
Reads public job boards from the hiring systems companies use for their careers pages.
Every fetcher returns the same shape:

    {"id", "title", "location", "department", "url", "posted_at", "text"}

posted_at is when the hiring system says the ad first went up (ISO, or None if it doesn't say).
text is a plain-text description when the system gives one cheaply, used only for keyword checks.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from . import __version__

HEADERS = {"User-Agent": f"GhostJobTracker/{__version__} (+https://github.com/monanyx/ghost-job-tracker)"}
SMARTRECRUITERS_CAP = 3000  # some boards list thousands; enough to judge the board


class BoardError(Exception):
    pass


def _get(url: str, params: dict | None = None, timeout: int = 40) -> requests.Response:
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 404:
                raise BoardError("board not found (404)")
            if r.status_code >= 400:
                raise BoardError(f"HTTP {r.status_code}")
            return r
        except BoardError as exc:
            if "404" in str(exc):
                raise
            last = exc
        except requests.RequestException as exc:
            last = exc
        time.sleep(3 * (attempt + 1))
    raise BoardError(str(last))


def _iso(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):  # Lever: milliseconds since 1970
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def greenhouse(board: str) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs").json()
    return [
        {
            "id": str(j["id"]),
            "title": j.get("title", "").strip(),
            "location": (j.get("location") or {}).get("name", ""),
            "department": "",
            "url": j.get("absolute_url", ""),
            "posted_at": _iso(j.get("first_published")),
            "text": "",
        }
        for j in data.get("jobs", [])
    ]


def lever(board: str) -> list[dict]:
    base = "https://api.eu.lever.co" if board.startswith("eu:") else "https://api.lever.co"
    board = board.removeprefix("eu:")
    data = _get(f"{base}/v0/postings/{board}", params={"mode": "json"}).json()
    if not isinstance(data, list):
        raise BoardError("unexpected response")
    return [
        {
            "id": j["id"],
            "title": j.get("text", "").strip(),
            "location": (j.get("categories") or {}).get("location", "") or "",
            "department": (j.get("categories") or {}).get("team", "") or "",
            "url": j.get("hostedUrl", ""),
            "posted_at": _iso(j.get("createdAt")),
            "text": " ".join(filter(None, [j.get("openingPlain"), j.get("descriptionPlain")]))[:4000],
        }
        for j in data
    ]


def ashby(board: str) -> list[dict]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{board}").json()
    return [
        {
            "id": j.get("id") or j.get("jobUrl", ""),
            "title": j.get("title", "").strip(),
            "location": j.get("location", "") or "",
            "department": j.get("department", "") or "",
            "url": j.get("jobUrl", ""),
            "posted_at": _iso(j.get("publishedAt")),
            "text": (j.get("descriptionPlain") or "")[:4000],
        }
        for j in data.get("jobs", [])
        if j.get("isListed", True)
    ]


def smartrecruiters(board: str) -> list[dict]:
    jobs, offset = [], 0
    while offset < SMARTRECRUITERS_CAP:
        data = _get(f"https://api.smartrecruiters.com/v1/companies/{board}/postings",
                    params={"limit": 100, "offset": offset}).json()
        batch = data.get("content", [])
        for j in batch:
            loc = j.get("location") or {}
            jobs.append({
                "id": str(j["id"]),
                "title": j.get("name", "").strip(),
                "location": loc.get("fullLocation") or ", ".join(filter(None, [loc.get("city"), loc.get("country", "").upper()])),
                "department": (j.get("department") or {}).get("label", "") or "",
                "url": f"https://jobs.smartrecruiters.com/{board}/{j['id']}",
                "posted_at": _iso(j.get("releasedDate")),
                "text": "",
            })
        offset += len(batch)
        if not batch or offset >= data.get("totalFound", 0):
            break
        time.sleep(0.3)
    return jobs


def personio(board: str) -> list[dict]:
    domain = "com" if board.endswith(".com") else "de"
    slug = board.removesuffix(".com").removesuffix(".de")
    r = _get(f"https://{slug}.jobs.personio.{domain}/xml")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        raise BoardError("board not found (no job feed)") from exc
    jobs = []
    for p in root.iter("position"):
        pid = (p.findtext("id") or "").strip()
        jobs.append({
            "id": pid,
            "title": (p.findtext("name") or "").strip(),
            "location": (p.findtext("office") or "").strip(),
            "department": (p.findtext("department") or "").strip(),
            "url": f"https://{slug}.jobs.personio.{domain}/job/{pid}",
            "posted_at": _iso((p.findtext("createdAt") or "").strip()),
            "text": "",
        })
    return jobs


FETCHERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "personio": personio,
}


def fetch_board(ats: str, board: str) -> list[dict]:
    if ats not in FETCHERS:
        raise BoardError(f"unknown hiring system '{ats}' (supported: {', '.join(FETCHERS)})")
    jobs = FETCHERS[ats](board)
    # Same id twice on one board happens (multi-location ads); keep the first.
    seen, unique = set(), []
    for j in jobs:
        if j["id"] and j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)
    return unique
