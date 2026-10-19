"""A demo site from made-up companies, so anyone can see the tracker without waiting for real history."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import tracker
from .signals import is_evergreen
from .site import build

COMPANIES = [
    ("haunted-labs", "Haunted Labs", [
        ("Senior Backend Engineer", "Berlin", 1460), ("Staff Product Designer", "Remote", 820),
        ("Data Scientist", "London", 610), ("Engineering Manager", "Berlin", 400),
        ("Talent Pool – Future Opportunities", "Anywhere", 900), ("Frontend Engineer", "Vienna", 45),
        ("Account Executive", "Paris", 210), ("Customer Success Manager", "Berlin", 130),
        ("Site Reliability Engineer", "Remote", 365), ("Product Manager", "London", 15),
        ("Mobile Engineer", "Remote", 520), ("Security Engineer", "Berlin", 95),
    ]),
    ("evergreen-corp", "Evergreen Corp", [
        ("Software Engineer", "New York", 2190), ("Software Engineer", "Austin", 1825),
        ("General Application", "Everywhere", 1300), ("Sales Development Rep", "Chicago", 400),
        ("Marketing Manager", "New York", 300), ("Recruiter", "Remote", 250),
        ("Analyst", "Chicago", 60), ("Designer", "Austin", 20), ("Support Specialist", "Remote", 190),
        ("Office Manager", "New York", 30), ("Finance Lead", "Chicago", 120),
    ]),
    ("freshly", "Freshly", [
        ("Backend Engineer", "Vienna", 12), ("Product Designer", "Vienna", 25), ("Data Engineer", "Graz", 40),
        ("Growth Marketer", "Vienna", 8), ("Customer Support", "Linz", 3), ("iOS Engineer", "Remote", 55),
        ("Office Lead", "Vienna", 20), ("Recruiter", "Vienna", 33), ("QA Engineer", "Graz", 70),
        ("Sales Lead", "Vienna", 14),
    ]),
]


def build_demo(out_root: Path) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    lines = ["site:", "  title: Ghost Job Tracker", "  demo: true", "companies:"]
    status = {}
    for cid, name, ads in COMPANIES:
        lines.append(f"  - {{ id: {cid}, name: \"{name}\", ats: greenhouse, board: {cid} }}")
        live = [{"id": f"{cid}-{i}", "title": t, "location": loc, "department": "",
                 "url": f"https://example.com/{cid}/jobs/{i}", "text": "",
                 "posted_at": (now - timedelta(days=age)).isoformat()} for i, (t, loc, age) in enumerate(ads)]
        state = {"jobs": {}, "history": []}
        if cid == "haunted-labs":
            # An earlier ad for the same role that closed, then came back as a "new" one = repost
            old = now - timedelta(days=700)
            tracker.update(state, [{"id": "hl-old", "title": "Data Scientist", "location": "London", "department": "",
                                    "url": "https://example.com/old", "text": "",
                                    "posted_at": (now - timedelta(days=1100)).isoformat()}],
                           old.isoformat(), evergreen_fn=is_evergreen)
            tracker.update(state, [], (now - timedelta(days=620)).isoformat())
        first = (now - timedelta(days=1)).isoformat()
        tracker.update(state, live, first, evergreen_fn=is_evergreen)
        if cid == "evergreen-corp":
            live[3]["posted_at"] = (now - timedelta(days=2)).isoformat()  # re-dated to look fresh
        tracker.update(state, live, now.isoformat(), evergreen_fn=is_evergreen)
        tracker.save(out_root, cid, state)
        status[cid] = {"ok": True, "last_checked": now.isoformat(), "name": name}
    (out_root / "companies.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_root / "data" / "status.json").write_text(json.dumps(status), encoding="utf-8")
    import ghostjobs.site as site_mod
    old_min, site_mod.MIN_RANKED = site_mod.MIN_RANKED, 3
    try:
        return build(out_root, out_root / "companies.yaml")
    finally:
        site_mod.MIN_RANKED = old_min
