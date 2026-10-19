"""Loads companies.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Company:
    id: str
    name: str
    ats: str
    board: str
    country: str = ""


def load(path: Path) -> tuple[dict, list[Company]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    s = raw.get("site") or {}
    site = {
        "title": s.get("title", "Ghost Job Tracker"),
        "url": str(s.get("url", "")).rstrip("/"),
        "repo": str(s.get("repo", "")).rstrip("/"),
        "demo": bool(s.get("demo", False)),
    }
    companies, seen = [], set()
    for c in raw.get("companies", []):
        cid = str(c["id"]).strip()
        if not SLUG.match(cid):
            raise ValueError(f"company id '{cid}' must be lowercase letters, digits and dashes")
        if cid in seen:
            raise ValueError(f"duplicate company id '{cid}'")
        seen.add(cid)
        companies.append(Company(id=cid, name=str(c.get("name", cid)), ats=str(c["ats"]).strip(),
                                 board=str(c["board"]).strip(), country=str(c.get("country", ""))))
    return site, companies
