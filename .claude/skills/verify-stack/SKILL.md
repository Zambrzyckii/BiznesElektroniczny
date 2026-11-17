---
name: verify-stack
description: Serial Docker verification of this repo's compose stack. Returns VERIFY PASS, FAIL or SKIPPED. Use after a change to deploy/ or shop/, and from issue-to-pr.
---

# verify-stack

You start the compose stack of this repo once, check it and remove it. The last line of your answer is exactly one of these.

- `VERIFY: PASS`
- `VERIFY: FAIL <check>` where `<check>` names the first failed check.
- `VERIFY: SKIPPED <reason>`

Never stop or touch other compose projects, such as `proj`. Never print resolved compose config and never read `.env`.

The compose file is `deploy/compose.yaml` in the worktree. Compose searches only the current directory and its parents, so every `docker compose` command runs as `cd <worktree>/deploy && docker compose ...`. Use the absolute worktree path from the dispatch and never your own checkout.

## 1. Preflight

Run one step at a time. Stop at the first step that refuses. Docker is not started before step 3 passes.

1. If `<worktree>/deploy/compose.yaml` does not exist, return `VERIFY: SKIPPED no compose file`. If it exists, run `cd <worktree>/deploy && docker compose config --quiet`. A failure there returns `VERIFY: FAIL compose config`.
2. Read `MemAvailable` from `/proc/meminfo`. It is in kB and independent of the locale. Under 3 GiB (3145728 kB) return `VERIFY: SKIPPED low memory`.
3. List the running compose project names with `docker compose ls -q`. Use the names only and never quote the config file paths that `docker compose ls` shows, because they hold private paths.
   - A project whose name starts with `be-` belongs to this repo. If one is running, return `VERIFY: SKIPPED another be- stack is running` and leave it as it is. A leftover `be-verify` from a crash or another session blocks every later run until the user removes it.
   - Projects with other names are information only. Mention their names in the answer and do nothing to them.

## 2. Run

1. Start the stack with `cd <worktree>/deploy && COMPOSE_PROJECT_NAME=be-verify docker compose up -d --wait`. From this point teardown is due. If it fails or a service is unhealthy, go to teardown and return `VERIFY: FAIL up`.
2. Run the checks for the services that exist in the compose file. Skip a check whose service is not there yet and say which ones you skipped.
   - Shop (issue #11). The shop answers with a success status on its URL.
   - Proxy (issue #13). Plain HTTP returns 301 to HTTPS.
   - Mailpit (issue #14). Its API lists the test message.
3. Read only status codes and short fields. Do not dump page bodies or environment values.

## 3. Teardown

Run it only when this run reached the `up` command in step 2, also after a failed check. After a preflight refusal there is nothing of yours to remove, and `down -v` would wipe the volumes of the stack that preflight said to leave alone.

1. Run `cd <worktree>/deploy && COMPOSE_PROJECT_NAME=be-verify docker compose down -v`. It removes only the `be-verify` project and its volumes.
2. Report the checks that ran, the ones skipped and the result line.
