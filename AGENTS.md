# AGENTS.md

University team project (4 people). A PrestaShop 8.2 shop in Docker, a Python scraper in `scraper/` and Playwright E2E tests in `tests/`. This file is for any AI coding tool. It lists only what you cannot read from the code.

## Commands

Run from `scraper/`.

- Install: `python -m pip install -r requirements.txt`
- Lint: `python -m ruff check .`
- Tests: `python -m pytest`

Shop commands (compose up, data init, backup) arrive with the issues that add `deploy/compose.yaml`. Until then do not invent them.

## Tests

- CI (`.github/workflows/scraper-ci.yml`) runs ruff and pytest on every PR and on every push to `main`.
- A PR is merged only with a green pipeline.
- Run ruff and pytest locally before saying a scraper change is done.

## Repository structure

- `shop/` shop code, theme, custom modules and the Dockerfile.
- `scraper/` scraper and its tests.
- `scraper-results/` scraping output in UTF-8 with image URLs and up to 20 sample images.
- `tests/` Playwright E2E tests.
- `deploy/` `compose.yaml` and scripts for install, data init, backup and restore.
- `docs/` the AI log in `AI_LOG.md` and architecture decisions in `docs/adr/`.

`shop/`, `scraper-results/`, `tests/` and `deploy/` are still empty placeholders.

## Style and language

The full rules are in `CONTRIBUTING.md`, except the simplicity rule below, which lives only here. These are broken most often.

- Code, file names, commits, branches and PR titles are English.
- Write the simplest code that solves the task and is easy to read. Prefer plain loops and conditionals to clever tricks, and accept a small performance cost for that. Add no abstraction, option or layer the task does not need.
- Issue and PR descriptions, reviews and documentation are Polish.
- A PR title is one imperative sentence of 3 to 8 words, capitalised, without a period, for example `Add shop Dockerfile for linux/amd64`.

## Git and pull requests

- Every task has an issue first. Do not work on an issue that has no assignee.
- Branch from current `main`, or from an unmerged parent issue branch under the stacked-branch rule in `CONTRIBUTING.md`. Name it `<issue-number>-<short-english-slug>`, for example `12-add-shop-dockerfile`.
- One PR closes one issue. Put `Closes #N` in the description.
- Fill `.github/pull_request_template.md`, including "Jak zweryfikowano" and "Czy użyto AI".
- A PR with significant AI-generated parts gets the `ai-assisted` label.
- Anyone who used AI adds a row to `docs/AI_LOG.md` in the same PR.
- Open unfinished work as a draft PR.
- Commits on the branch can be rough. The PR is squash-merged and only its title remains.

## Boundaries

### Always

- Verify before saying done. Run the checks that cover the change and show the output (ruff and pytest for scraper changes).
- Change the docs in the same PR as the code they describe. A PR that changes how the shop starts updates the "Uruchomienie" section of `README.md`.
- Add new generated files to `.gitignore` and new environment variables to `.env.example`.

### Ask first

- Adding a dependency.
- Deleting files.
- Changing CI workflows.
- Changing the compose service layout.

### Never

- Read or print `.env`, or print resolved compose config. `docker compose config` is allowed only with `--quiet`.
- Commit secrets, files over 10 MB or the full set of product images.
- Paste passwords, API keys or access data into an AI tool.
- Push to `main`.
- Force push, except `git push --force-with-lease` on a feature branch when a human asks for it after a stacked-branch rebase.
- Approve or merge PRs. The author merges after a human review.
