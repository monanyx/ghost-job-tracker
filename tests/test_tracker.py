"""Tests with made-up job boards — no network needed."""

import json
from pathlib import Path

import pytest

from ghostjobs import runner, tracker
from ghostjobs.signals import analyze, company_summary, is_evergreen


def ad(i, title="Backend Engineer", loc="Vienna", posted="2026-01-01T00:00:00+00:00"):
    return {"id": str(i), "title": title, "location": loc, "department": "", "url": f"https://x/{i}",
            "posted_at": posted, "text": ""}


def test_new_closed_reopened_redated():
    st = {"jobs": {}, "history": []}
    m = tracker.update(st, [ad(1), ad(2)], "2026-02-01T00:00:00+00:00")
    assert m["new"] == 2
    m = tracker.update(st, [ad(1)], "2026-02-02T00:00:00+00:00")
    assert m["closed"] == 1 and st["jobs"]["2"]["closed_at"]
    m = tracker.update(st, [ad(1, posted="2026-02-03T00:00:00+00:00"), ad(2)], "2026-02-03T00:00:00+00:00")
    assert m["reopened"] == 1 and m["redated"] == 1
    assert st["jobs"]["1"]["posted_history"] == ["2026-01-01T00:00:00+00:00", "2026-02-03T00:00:00+00:00"]


def test_repost_keeps_the_true_age():
    st = {"jobs": {}, "history": []}
    tracker.update(st, [ad(1, "Data Scientist (m/w/d)", "London", "2025-01-01T00:00:00+00:00")], "2025-01-02T00:00:00+00:00")
    tracker.update(st, [], "2025-06-01T00:00:00+00:00")  # ad disappears
    # comes back as a brand-new ad, freshly dated
    tracker.update(st, [ad(9, "Data Scientist", "London", "2025-07-01T00:00:00+00:00")], "2025-07-02T00:00:00+00:00")
    [j] = analyze(st, "2026-01-02T00:00:00+00:00")
    assert j["reposts"] == 1
    assert j["since"] == "2025-01-01"           # not the fresh 2025-07-01 date the board shows
    assert j["age_days"] == 366 and j["score"] >= 4


def test_evergreen_words():
    assert is_evergreen("Sales Talent Pool - German Speaker (all genders)")
    assert is_evergreen("[Expression of Interest] Research Engineer")
    assert is_evergreen("Initiativbewerbung")
    assert is_evergreen("Engineer", "This is an evergreen role for future openings")
    assert not is_evergreen("Data Pipeline Engineer")
    assert not is_evergreen("Senior Software Engineer")


def test_summary_and_scores():
    st = {"jobs": {}, "history": []}
    tracker.update(st, [ad(1, posted="2024-01-01T00:00:00+00:00"), ad(2, "PM", posted="2026-09-01T00:00:00+00:00")],
                   "2026-10-01T00:00:00+00:00", evergreen_fn=is_evergreen)
    jobs = analyze(st, "2026-10-19T00:00:00+00:00")
    s = company_summary(jobs)
    assert s["open"] == 2 and s["pct_90"] == 50 and s["oldest"] > 1000


def test_empty_board_is_not_mass_closure(tmp_path, monkeypatch):
    cfile = tmp_path / "companies.yaml"
    cfile.write_text("companies:\n  - { id: acme, name: Acme, ats: greenhouse, board: acme }\n")
    monkeypatch.setattr(runner, "fetch_board", lambda ats, b: [ad(i) for i in range(8)])
    runner.run(tmp_path, cfile, pause=0)
    monkeypatch.setattr(runner, "fetch_board", lambda ats, b: [])
    runner.run(tmp_path, cfile, pause=0)
    state = tracker.load(tmp_path, "acme")
    assert all(not r["closed_at"] for r in state["jobs"].values())
    assert json.loads((tmp_path / "data/status.json").read_text())["acme"]["ok"] is False


def test_demo_site_builds(tmp_path):
    from ghostjobs.demo import build_demo
    out = build_demo(tmp_path)
    index = (out / "index.html").read_text()
    assert "Evergreen Corp" in index and "Oldest job ad still online" in index
    page = (out / "c" / "haunted-labs.html").read_text()
    assert "reposted 1×" in page
    assert "re-dated" in (out / "c" / "evergreen-corp.html").read_text()
