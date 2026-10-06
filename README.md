# Kenyon Baseball Alumni CMS

IPHS 400 Mini-Project #2. I built a  small web CMS for the Kenyon College Varsity Baseball Team Alumni. A private admin console on the Head Coach's laptop writes content;`cms publish` renders only the published content into plain static HTML, which is deployed to GitHub Pages. The admin console is never put on the public internet (see `docs/adr/ADR-001-local-admin-static-public.md`).

## Live URL

https://samuelphodges.github.io/iphs400-mp2-cms/

## Run locally

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/samuelphodges/iphs400-mp2-cms.git
cd iphs400-mp2-cms
uv sync
cp .env.example .env                    # then edit the secrets in .env
set -a && . ./.env && set +a            # load .env into this shell
uv run python scripts/seed_demo.py      # demo users, pages, posts and listings
uv run cms serve                        # admin console at http://localhost:8000/login
```

Demo accounts (passwords are the `CMS_ADMIN_PASSWORD` and `CMS_EDITOR_PASSWORD`
values in `.env`):

| Role | Email | Can do |
|---|---|---|
| Admin (Head Coach, Matt) | `admin@example.test` | everything, including the Locked Team Schedule and Users |
| Editor (Second Editor, Joe) | `editor@example.test` | write and publish content and Listings; cannot edit Locked pages or manage users |

Publish and deploy the public site:

```bash
uv run cms publish      # renders published content into site/ (relative paths only)
uv run cms deploy       # pushes site/ to the gh-pages branch
```

Run the tests and the type check:

```bash
uv run pytest
uv run mypy app scripts
```

## What is here

```text
app/             FastAPI app: routes, data access, Markdown sanitising, publish
templates/       Jinja templates for the admin console and the public site
scripts/         seed_demo.py, usage_report.py, check_submission.py
tests/           one test file per ticket (test_t01 to test_t08) plus helpers
CONTEXT.md       the project glossary
docs/adr/        decisions that are hard to undo
docs/screenshots/ the six admin screens at 1280 px and 390 px
docs/transcripts/ every Claude Code session
notes/           field notes, client brief, token budget plan and usage ledger
```

## Generative AI Use Statement

**Models and tools.** Claude Code with Claude Sonnet 5.5 for essentially every
session (the usage ledger in `notes/usage-ledger.csv` records 149 of 151 turns on
Sonnet 5.5 and 2 on Sonnet 5). Skills from the `mattpocock/skills` set: grilling,
spec, tickets, `/implement` with `/tdd`, and `/code-review`. The code for this project was written by Claude from the information from the grill, spec, and tickets. I gave Claude the client brief and context needed in order to work through the project. I also gave Claude the client scope and grill decisions to fit my CMS to my client's needs. 

**Two prompts I used.**

1. "1. (a) but i want the schedule page to be named "Team Schedule" and the events page to be named "ALumni Events". 2 (a). 3. I like (c) as it gives the most privacy but everyone can still see the names of alumni. 4. The combo of (b0 and (a) you suggest seems most reasonable. 5. Yes Joe can publish on those sections without Matt's approval."
2. "1. Yes that order is good. 2. Lets use Sonnet and medium effort. 3. Yes. -- Lets go with that suggested order of 5 steps and go one by one"-- In this prompt I was working through the budget planning steps and I prompted Claude to separate the tasks ahead into separate steps rather than run them all at once. 

**One real model failure.**
- In T01 the model wrote a test that claimed to check every admin route redirects anonymous visitors, but it only saw two routes because it read app.routes, which hides routes added with include_router. It passed for seven tickets without checking most of the app. It was only caught in T08, when moving /admin into a router broke it, and the fix was to read the routes from the OpenAPI schema instead. This fix was thus conducted much later than it should've been. I did not notice the issue due to its subtlety but Claude caught it much later on. 

**Backends used.**

| Backend | Used for | Notes |
|---|---|---|
| Anthropic (Claude Code, Sonnet 5.5) | all sessions | the ledger's `provider` column is `anthropic` for every row |

No backup provider was used, so there are no Backend: trailers
