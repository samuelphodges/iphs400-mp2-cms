# Handoff: tickets approved, not yet published

**Date:** 2026-10-04 · **Phase:** `tickets` (see `.claude/state/phase`)

## State

- Grill is done. `CONTEXT.md` has the glossary (15 terms), and ADR-003 is written.
- Spec is published as issue #1 (labels `spec`, `ready-for-agent`). The user confirmed the
  five defaults listed in its Further Notes.
- Labels `spec`, `ticket`, `stretch`, `ready-for-agent`, `needs-triage`, `needs-info` and
  `ready-for-human` exist on the repo.
- The user approved the 8-ticket breakdown below. **None are published yet.**

## Update, 2026-10-05

The tickets were published later: T01-T08 are issues #2-#9 (T0N is issue #N+1). The "Next step"
below is done. Start implementing at T01 (#2).

## Next step (done)

Publish the tickets with `/to-tickets` (or by hand with `gh issue create`), in dependency order, labelled `ticket` and
`ready-for-agent`, each with a "What to build", "Acceptance criteria" and a "Blocked by"
section using real issue numbers. Use the title form `T0N: ...`. Do not close or edit issue #1.

## Approved breakdown

| Ticket | Title | Blocked by |
|---|---|---|
| T01 | Matt and Joe can sign in and out | None |
| T02 | Editors can write, preview and manage pages | T01 |
| T03 | Publish pages to the public site and put it on GitHub Pages | T02 |
| T04 | Editors can write Events and Team Updates | T02, T03 |
| T05 | Only Matt can change Locked pages | T02 |
| T06 | Matt can manage users | T01 |
| T07 | Joe can keep the Alumni Network, with names only | T03 |
| T08 | Dashboard, hardening and demo data | T04, T05, T06, T07 |

- **T01:** seeded Matt (admin) and Joe (editor); argon2; login/logout; wrong-password message; anonymous redirect; CSRF on the login form.
- **T02:** Page CRUD; generated, editable slug; sanitized Markdown preview; success/error messages; first content list of pages.
- **T03:** `cms publish` writes only published pages with relative paths; Home first, the other pages alphabetical in the nav; deploy to Pages. Needed for Stage 1 "live on Pages".
- **T04:** Post CRUD with required Post Type (Event default for Joe); list filters by status and type; Alumni Events lists Events newest first; Home shows 3 Team Updates and 3 recent Events.
- **T05:** Locked flag, set on the Team Schedule; Joe can open but is refused edit, publish, unpublish and delete; only Matt sees lock/unlock; access-control tests that enumerate admin-only routes from the router.
- **T06:** Users screen (admin only): create, change role, deactivate/reactivate; deactivated users cannot log in; Matt cannot deactivate or demote himself; users are never deleted.
- **T07:** Listing CRUD (name, email, optional class year, consent date, recorded-by); publish adds the alphabetical consented names and the Alumni Contact Line; a test asserts no email appears in `site/`.
- **T08:** dashboard counts; persistent admin nav; CSRF replay test per form; link and relative-path check on the whole export; seed script runs clean from `.env.example`; 390 px width check.

## Open questions the user raised

- Granularity: T04 could split into "Posts CRUD and list filters" and "Posts on Home and Alumni Events". User said granularity felt right; keep as is unless a ticket overruns its context.

## Reminders

- Save this session's transcript to `docs/transcripts/` (naming pattern in the rubric).
- Stage 1 needs T01-T03 closed (each with a `/code-review` comment before close) and a live Pages item.
- One ticket per fresh session; `/clear` between tickets.
