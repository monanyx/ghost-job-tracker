"""
Usage:
  python -m ghostjobs run                 read every job board, record what changed, rebuild the site
  python -m ghostjobs run --only stripe
  python -m ghostjobs build               rebuild the site from saved data
  python -m ghostjobs check ATS BOARD     test a job board before adding it
  python -m ghostjobs demo                demo site from made-up companies
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="ghostjobs", description="Ghost Job Tracker")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--companies", type=Path, default=None, help="default: ROOT/companies.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--only")
    p_run.add_argument("--no-site", action="store_true")
    sub.add_parser("build")
    p_check = sub.add_parser("check")
    p_check.add_argument("ats")
    p_check.add_argument("board")
    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--out", type=Path, default=Path("demo-site"))
    args = parser.parse_args()
    companies = args.companies or args.root / "companies.yaml"

    if args.cmd == "run":
        from .runner import run
        run(args.root, companies, only=args.only)
        if not args.no_site:
            from .site import build
            build(args.root, companies)
    elif args.cmd == "build":
        from .site import build
        build(args.root, companies)
    elif args.cmd == "check":
        from .ats import fetch_board
        jobs = fetch_board(args.ats, args.board)
        dated = [j for j in jobs if j["posted_at"]]
        print(f"{len(jobs)} open ads, {len(dated)} with a posting date")
        for j in sorted(dated, key=lambda j: j["posted_at"])[:10]:
            print(f"  since {j['posted_at'][:10]}  {j['title']} — {j['location']}")
    elif args.cmd == "demo":
        from .demo import build_demo
        print(f"demo site → {build_demo(args.out)}/index.html")


if __name__ == "__main__":
    main()
