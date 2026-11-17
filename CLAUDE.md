@AGENTS.md

# Claude Code

This section is read only by Claude. The agents live in `.claude/agents/` and the skills in `.claude/skills/`.

## Agents

- `planner` use first for a non-trivial issue. It reads the issue and the code and returns a plan with the open decisions listed.
- `implementer` use to carry out one approved plan or one fix round, with tests and docs for its change.
- `reviewer` use for an independent read of a diff. It starts from the code, not from the author's conclusions.
- `docs-writer` use to update README, ADRs or other docs so they match the code.

## Skills

- `issue-to-pr` manual route from an issue to a draft PR description, without pushing. It runs planner, a decision gate on open decisions, implementer, `verify-stack`, reviewer and docs-writer.
- `verify-stack` serial Docker verification of this repo's compose stack.

## Docker

Only one Docker stack of this repo runs at a time, and only through `verify-stack`. Never start a second stack in parallel and never run `docker compose up` by hand.
