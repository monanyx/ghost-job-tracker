# 👻 Ghost Job Tracker

**That job ad has been up for 17 years. Nobody's hiring.**

Every night, Ghost Job Tracker reads the public job boards of 77 companies (OpenAI, Anthropic, Stripe, SpaceX, Airbnb, Spotify, Bosch, Bitpanda, GoStudent and more) and remembers every ad it has ever seen. Then it shows which ads never close.

On the first run it already found:

- **Palantir:** a "Forward Deployed Software Engineer, London" ad first published in **2009** and still up
- **Zoox:** a Software Engineer ad up for **10+ years**
- **962** ads that have been online for **more than a year**, out of 19,557
- Ads that admit it in the title: "Talent Pool", "Expression of Interest", "Future Opportunities", "Open Application"

No accounts, no servers, no cost. It runs on GitHub Actions and publishes to GitHub Pages.

## Where the data comes from

Most careers pages run on a hiring system that publishes every open ad as public data, including the date it was first posted:

| Hiring system | Posting date from |
|---|---|
| Greenhouse | `first_published` |
| Lever | `createdAt` |
| Ashby | `publishedAt` |
| SmartRecruiters | `releasedDate` |
| Personio | `createdAt` |

No scraping of LinkedIn or job sites, no logins.

## Ghost signals

| Signal | Meaning |
|---|---|
| **Up for** | The oldest date we can prove the ad has existed |
| **Reposted** | Same role, same place, closed and came back as a "new" ad |
| **Re-dated** | Same ad, but its posting date moved forward so it looks fresh |
| **Says "talent pool"** | The ad itself says it's for future openings or a talent pool |

These add up to a **ghost score** from 0 to 5 per ad, and a **ghost index** from 0 to 100 per company. The full method is on the site's *How it works* page.

An old ad isn't proof a job is fake. It's proof the ad is old. That's still worth knowing before you spend an evening on a cover letter.

## Add a company

One line in `companies.yaml`:

```yaml
  - { id: acme, name: "Acme", ats: greenhouse, board: acme }
```

Find the board name in the company's careers page address (`job-boards.greenhouse.io/acme`, `jobs.lever.co/acme`, `jobs.ashbyhq.com/acme`, …), then test it:

```bash
python -m ghostjobs check greenhouse acme
```

## Run it yourself

```bash
pip install -r requirements.txt
python -m ghostjobs run            # read every board, save changes, build the site in docs/
python -m ghostjobs run --only stripe
python -m ghostjobs demo           # demo site from made-up companies → demo-site/docs/
python -m pytest -q
```

## How it runs

- **Every night** (GitHub Actions): read all boards → save changes to `data/` → build the site → publish to GitHub Pages
- `data/companies/<id>.json` keeps every ad ever seen. It only changes when something happens, so the git history is a clean log of which ads opened, closed, came back or got re-dated.
- `/api/leaderboard.json`, `/api/oldest.json` and `/api/<company>.json` on the site, for anyone who wants to build on the data.

## Part of the side-eye suite

1. [ToS Night Shift](https://github.com/monanyx/tos-night-shift): catches companies quietly changing their Terms of Service
2. **Ghost Job Tracker**
3. What Did That App Just Say: coming
4. Payslip Checker: coming

MIT licensed.
