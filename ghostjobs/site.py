"""Builds the public website in docs/: leaderboard, oldest ads, one page per company, method, JSON API."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import tracker
from .config import load
from .runner import status_path
from .signals import analyze, company_summary, now_iso

TEMPLATES = Path(__file__).parent / "templates"
GENERATED = ["index.html", "method.html", "c", "api", ".nojekyll"]
MIN_RANKED = 10       # boards smaller than this aren't ranked — one old ad shouldn't top the chart
MAX_ROWS = 400        # per company page; the rest are in the JSON
BUCKETS = [("< 1 mo", 0, 30), ("1–3 mo", 30, 90), ("3–6 mo", 90, 180), ("6–12 mo", 180, 365), ("1 yr +", 365, 10**6)]


def human_age(days: int) -> str:
    if days >= 730:
        return f"{days / 365.25:.0f} years" if days >= 1095 else f"{days / 365.25:.1f} years"
    if days >= 365:
        return "1 year" if days < 425 else f"{days / 365.25:.1f} years"
    if days >= 60:
        return f"{round(days / 30.44)} months"
    if days >= 30:
        return "1 month"
    return f"{days} day{'s' if days != 1 else ''}"


def build(root: Path, companies_file: Path) -> Path:
    site, companies = load(companies_file)
    sp = status_path(root)
    status = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    now = now_iso()

    out = root / "docs"
    out.mkdir(parents=True, exist_ok=True)
    for name in GENERATED:
        t = out / name
        if t.is_dir():
            shutil.rmtree(t)
        elif t.exists():
            t.unlink()

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["age"] = human_age
    env.filters["num"] = lambda n: f"{n:,}"

    boards, everything = [], []
    for c in companies:
        jobs = analyze(tracker.load(root, c.id), now)
        s = company_summary(jobs)
        buckets = [{"label": lbl, "n": sum(lo <= j["age_days"] < hi for j in jobs)} for lbl, lo, hi in BUCKETS]
        st = status.get(c.id, {})
        boards.append({"id": c.id, "name": c.name, "ats": c.ats, "country": c.country, "summary": s,
                       "buckets": buckets, "jobs": jobs, "ok": st.get("ok", True), "error": st.get("error"),
                       "page": f"c/{c.id}.html"})
        everything += [dict(j, company=c.name, company_id=c.id) for j in jobs]

    ranked = sorted([b for b in boards if b["summary"]["open"] >= MIN_RANKED],
                    key=lambda b: (-b["summary"]["ghost_index"], -b["summary"]["median_age"]))
    small = sorted([b for b in boards if 0 < b["summary"]["open"] < MIN_RANKED], key=lambda b: b["name"])
    broken = [b for b in boards if not b["ok"]]
    oldest = sorted(everything, key=lambda j: -j["age_days"])[:30]
    evergreen = [j for j in everything if j["evergreen"]][:40]

    total = len(everything)
    over_year = sum(j["age_days"] >= 365 for j in everything)
    over_90 = sum(j["age_days"] >= 90 for j in everything)
    hours_checked = max((s.get("last_checked", "") for s in status.values()), default="")
    common = {"site": site, "n_companies": len(companies), "n_jobs": total, "over_year": over_year,
              "pct_90": round(100 * over_90 / total) if total else 0, "last_run": hours_checked[:10],
              "min_ranked": MIN_RANKED}

    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "index.html").write_text(env.get_template("index.html").render(
        **common, root="", ranked=ranked, small=small, broken=broken, oldest=oldest, evergreen=evergreen,
        top=oldest[0] if oldest else None), encoding="utf-8")
    (out / "method.html").write_text(env.get_template("method.html").render(**common, root=""), encoding="utf-8")

    (out / "c").mkdir()
    tpl = env.get_template("company.html")
    for b in boards:
        (out / b["page"]).write_text(tpl.render(**common, root="../", b=b, rows=b["jobs"][:MAX_ROWS],
                                                hidden=max(0, len(b["jobs"]) - MAX_ROWS)), encoding="utf-8")

    (out / "api").mkdir()
    (out / "api" / "leaderboard.json").write_text(json.dumps(
        [{"company": b["name"], "id": b["id"], **b["summary"]} for b in ranked + small], indent=1), encoding="utf-8")
    (out / "api" / "oldest.json").write_text(json.dumps(oldest, indent=1, ensure_ascii=False), encoding="utf-8")
    for b in boards:
        (out / "api" / f"{b['id']}.json").write_text(json.dumps(b["jobs"], ensure_ascii=False), encoding="utf-8")

    print(f"site: {total:,} open ads from {len(companies)} companies → {out}")
    return out
