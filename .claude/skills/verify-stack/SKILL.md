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

## 1. Preflight

Run from the worktree root, one step at a time. Stop at the first step that refuses.

1. Run `docker compose config --quiet`. If no compose file exists yet, return `VERIFY: SKIPPED no compose file`. If the command fails, return `VERIFY: FAIL compose config`.
2. Read `MemAvailable` from `/proc/meminfo`. It is in kB and independent of the locale. Under 3 GiB (3145728 kB) return `VERIFY: SKIPPED low memory`.
3. List running compose projects with `docker compose ls`.
   - A project whose name starts with `be-` belongs to this repo. If one is running, return `VERIFY: SKIPPED another be- stack is running` and leave it as it is.
   - Projects with other names are information only. Mention them in the answer and do nothing to them.

## 2. Run

1. Start the stack with `COMPOSE_PROJECT_NAME=be-verify docker compose up -d --wait`. If it fails or a service is unhealthy, go to teardown and return `VERIFY: FAIL up`.
2. Run the checks for the services that exist in the compose file. Skip a check whose service is not there yet and say which ones you skipped.
   - Shop (issue #11). The shop answers with a success status on its URL.
   - Proxy (issue #13). Plain HTTP returns 301 to HTTPS.
   - Mailpit (issue #14). Its API lists the test message.
3. Read only status codes and short fields. Do not dump page bodies or environment values.

## 3. Teardown

Always run it, also after a failure.

1. Run `COMPOSE_PROJECT_NAME=be-verify docker compose down -v`. It removes only the `be-verify` project and its volumes.
2. Report the checks that ran, the ones skipped and the result line.
