# ADR-003: Alumni Listings are a separate type; emails are stored but never published

**Status:** accepted
**Date:** 2026-10-04

## Context

The client wants an opt-in alumni contact list. Alumni cannot log in, so the Second
Editor records each alumnus's consent. The public site is static on GitHub Pages:
anything published is readable by anyone, including scrapers. The manual's content
types are Posts and Pages, and neither has a field for consent. Options considered:
a public list with emails, obfuscated emails, names only with a contact path, and a
Markdown page typed by hand.

## Decision

An alumnus's entry is a **Listing**, a third content type with name, email, optional
class year, consent date, and who recorded it. Only Listings with consent are
exported, and only their **names** reach `site/`. Emails stay in the database. The
public Alumni Network page carries one Alumni Contact Line telling visitors to email
the Second Editor, who introduces them to the alumnus.

## Consequences

- The exporter never reads the email field, so a test can assert that no alumnus
  email appears anywhere in `site/`.
- Removing a Listing or withdrawing consent removes the name at the next publish,
  with no leftover text in a page body.
- An extra model, admin screen, and exporter step are needed beyond Posts and Pages.
- Visitors cannot contact an alumnus directly. The Second Editor is a manual go-between.
- Once names are published to GitHub Pages they may be cached or indexed, so
  withdrawal cannot recall a name already published.

## Why this is an ADR

It is hard to reverse (the model and the exporter both depend on it), surprising
without context (the manual lists only Posts and Pages), and the result of a real
trade-off between findability and the privacy the client asked for.
