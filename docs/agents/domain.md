# Domain Docs

How the engineering skills should consume this repo's domain documentation. Layout: **single-context**.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root: the project's domain language.
- **`docs/DECISIONS.md`**: the decision log. This repo keeps decisions in one append-only file instead of `docs/adr/` (see D-019). Read the entries that touch the area you're about to work in.
- **`docs/plan/03-no-lookahead.md`** before touching data, features, models or backtests.

## Recording decisions

When a skill would create an ADR in `docs/adr/`, append a new `D-NNN` entry to `docs/DECISIONS.md` instead, using the format at the top of that file. Never rewrite a past entry; supersede it with a new one.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts an entry in `docs/DECISIONS.md`, surface it explicitly rather than silently overriding:

> _Contradicts D-014 (12-month vault), but worth reopening because…_
