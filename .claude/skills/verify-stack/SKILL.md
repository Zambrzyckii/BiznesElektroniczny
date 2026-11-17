---
name: verify-stack
description: Serial Docker verification of this repo's compose stack. Returns VERIFY PASS, FAIL or SKIPPED. Use after a change to deploy/ or shop/, and from issue-to-pr.
---

# verify-stack

You start the compose stack of this repo once, check it and remove it. The last line of your answer is exactly one of these.

- `VERIFY: PASS`
- `VERIFY: FAIL <check>` where `<check>` names the first failed check.
- `VERIFY: SKIPPED <reason>`

Never stop or touch other compose projects, such as `proj`. Never print resolved compose config. Never create, copy or read `.env`. Check only whether `deploy/.env` exists, with `test -e`.

The compose file is `deploy/compose.yaml` in the worktree. Compose searches only the current directory and its parents, so every `docker compose` command runs as `cd <worktree>/deploy && docker compose ...`. Use the absolute worktree path from the dispatch and never your own checkout.

## 1. Preflight

Run one step at a time. Stop at the first step that refuses. Docker is not started before step 4 passes.

1. If `<worktree>/deploy/compose.yaml` does not exist, return `VERIFY: SKIPPED no compose file`. If it exists, check `test -e <worktree>/deploy/.env`. When the compose file needs `.env` (it declares `env_file: .env` or interpolates a `${VAR}` without a default) and the file does not exist, return `VERIFY: SKIPPED no .env`. Otherwise run `cd <worktree>/deploy && docker compose config --quiet`. A failure there returns `VERIFY: FAIL compose config`. When the failure says a variable is missing a value, return `VERIFY: SKIPPED .env lacks <name>` instead and tell the user to copy that line from `deploy/.env.example` into `deploy/.env`, because only he edits that file.
2. Take the lock, so that sessions running in parallel use Docker one after another. Run `timeout 450 bash -c 'until mkdir /tmp/be-verify.lock 2>/dev/null; do sleep 20; done'` with a Bash timeout of 600000 ms, and once more if it times out. After two timeouts return `VERIFY: SKIPPED lock busy for 15 minutes`. Tell the user that a crashed session can leave the lock and a `be-verify` stack behind, and that he removes them with `rmdir /tmp/be-verify.lock` and `cd <worktree>/deploy && COMPOSE_PROJECT_NAME=be-verify docker compose down -v`. From here on, every return of yours first runs `rmdir /tmp/be-verify.lock`.
3. Read `MemAvailable` from `/proc/meminfo`. It is in kB and independent of the locale. Under 3 GiB (3145728 kB) return `VERIFY: SKIPPED low memory`.
4. List the running compose project names with `docker compose ls -q`. Use the names only and never quote the config file paths that `docker compose ls` shows, because they hold private paths.
   - A project whose name starts with `be-`, or is named `deploy` (a stack started from `deploy/` without a `name:`), belongs to this repo. If one is running, return `VERIFY: SKIPPED another stack of this repo is running` and leave it as it is. A leftover `be-verify` from a crash or another session blocks every later run until the user removes it.
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
2. Release the lock with `rmdir /tmp/be-verify.lock`.
3. Report the checks that ran, the ones skipped and the result line.
