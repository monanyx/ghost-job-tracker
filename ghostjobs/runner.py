"""The nightly check: read every job board, remember what changed."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import tracker
from .ats import BoardError, fetch_board
from .config import load
from .signals import is_evergreen, now_iso


def status_path(root: Path) -> Path:
    return root / "data" / "status.json"


def run(root: Path, companies_file: Path, only: str | None = None, pause: float = 0.5) -> dict:
    _, companies = load(companies_file)
    sp = status_path(root)
    status = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    now = now_iso()
    tally = {"companies": 0, "jobs": 0, "new": 0, "closed": 0, "reopened": 0, "redated": 0, "errors": 0}

    for c in companies:
        if only and c.id != only:
            continue
        st = status.setdefault(c.id, {})
        st.update(name=c.name, ats=c.ats, board=c.board, last_checked=now)
        try:
            live = fetch_board(c.ats, c.board)
        except BoardError as exc:
            st.update(ok=False, error=str(exc))
            tally["errors"] += 1
            print(f"✗ {c.name}: {exc}", flush=True)
            continue

        state = tracker.load(root, c.id)
        was_open = sum(1 for r in state["jobs"].values() if not r.get("closed_at"))
        if not live and was_open >= 5:
            # A board doesn't go from 40 ads to zero overnight — treat it as a glitch, not mass closures.
            st.update(ok=False, error=f"board returned 0 ads (had {was_open}) — skipped tonight")
            tally["errors"] += 1
            print(f"? {c.name}: empty board, skipped", flush=True)
            continue

        moved = tracker.update(state, live, now, evergreen_fn=is_evergreen)
        tracker.save(root, c.id, state)
        st.update(ok=True, error=None, open=len(live))
        tally["companies"] += 1
        tally["jobs"] += len(live)
        for k in ("new", "closed", "reopened", "redated"):
            tally[k] += moved[k]
        print(f"· {c.name}: {len(live)} open  (+{moved['new']} new, −{moved['closed']} gone, "
              f"{moved['reopened']} back, {moved['redated']} re-dated)", flush=True)
        time.sleep(pause)

    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(status, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    summary = "  ".join(f"{k}: {v}" for k, v in tally.items())
    print("\n" + summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"## 👻 Ghost Job Tracker\n\n{summary}\n")
    return tally
