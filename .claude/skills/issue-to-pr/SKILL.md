---
name: issue-to-pr
description: Manual route from one issue to a draft PR description. Creates a worktree, then runs planner, a decision gate, implementer, verify-stack, reviewer and docs-writer.
disable-model-invocation: true
argument-hint: <issue-number> [base-branch]
---

# issue-to-pr

You are the controller. You run the route below for issue `$ARGUMENTS[0]`. The base branch is `$ARGUMENTS[1]`, or `origin/main` when it is empty. You dispatch the agents in `.claude/agents/` and write no code yourself.

## Rules for the whole route

- Never create or edit an issue. Reading one is allowed.
- The repo may be local only. Push and open a PR only when the user explicitly says so. Until then you prepare the draft PR description and the AI_LOG row and stop.
- Give every dispatch the absolute worktree path, the branch name and the full issue text. A subagent starts in another checkout and its cwd resets between calls.
- A worktree branched from `origin/main` can lack `AGENTS.md` until the AI layer is merged. When it does, give every dispatch to `planner`, `implementer`, `reviewer` and `docs-writer` the absolute path of `AGENTS.md` in your own checkout as required reading.
- Run one `verify-stack` at a time and give it the absolute worktree path, so it never runs against your own checkout. Never start Docker by hand.

## Steps

1. Read the issue.
   - Run `gh issue view <n>` (read-only) or use the text the user pasted.
   - Stop if the issue has no assignee, as `AGENTS.md` requires, and ask the user.
   - Note the acceptance criteria. Reviewer and docs-writer need them.

2. Create the worktree.
   - Choose a branch name `<issue-number>-<short-english-slug>`.
   - Run `git worktree add <path> -b <issue-number>-<slug> <base branch>` from your checkout. Put `<path>` outside the checkout, next to it.
   - The base branch defaults to `origin/main`. When the user gives another branch, this is a stacked branch (see step 9).
   - Do not rely on the agent `isolation` default. The worktree is always created here, so every agent works on a known path and branch.

3. Dispatch `planner`.
   - Brief: the issue text, the repo path to read, and the `AGENTS.md` path when the worktree lacks one.
   - It returns the sections Files, Steps, Acceptance checks, Verification, Docs to update, AI_LOG row draft and Open decisions.

4. Decision gate.
   - If `## Open decisions` is not `None`, stop. Show the decisions with their options and the planner's recommendation to the user and wait for the answer.
   - Put the answers into the brief before step 5. Anything in the planner's "Ask first" list that the user did not approve stays out of the plan.
   - Mark the answers that bind teammates, such as the settings method or the ports. They are flagged in the PR description for team discussion (steps 8 and 9).

5. Dispatch `implementer` with the approved Files and Steps.
   - The dispatch must name both the absolute worktree path and the branch name. The agent prefixes every Bash command with `cd <worktree-path> &&` and stops when `cd <worktree-path> && git branch --show-current` differs from the branch you gave.
   - Add the `AGENTS.md` path when the worktree lacks one.
   - Run several implementers in parallel only for independent issues, each in its own worktree. Steps of one plan run in order.
   - Read its report. `Status: DONE` or `DONE_WITH_CONCERNS` moves on. `NEEDS_CONTEXT` or `BLOCKED` goes back to the planner or to the user. Never push past a blocked status.

6. Run `verify-stack` when the change touches `deploy/` or `shop/`.
   - Pass it the absolute worktree path. Act on its result line.
   - `VERIFY: FAIL <check>` goes to the implementer as a fix round. Rerun `verify-stack` after the fix. Do not go to step 7 while the result is `FAIL`.
   - `VERIFY: SKIPPED <reason>` is recorded in the PR description as not verified, with the reason.

7. Dispatch `reviewer`.
   - The reviewer has only Read, Grep and Glob, so it cannot run git. Prepare its input first. From the worktree, write one file with `git log --oneline <base>..HEAD`, then `git diff --stat <base>..HEAD`, then `git diff -U10 <base>..HEAD`. Put it in a temp path (`mktemp`) or in a git-ignored scratch area of the worktree, never in a tracked path.
   - Dispatch with that file path, the issue's acceptance criteria, the worktree path and the `AGENTS.md` path when the worktree lacks one. Do not pass the implementer's conclusions.
   - `Verdict: APPROVE` moves on, with the minors noted.
   - `Verdict: CHANGES_REQUESTED` starts a fix round. Send the findings to `implementer` as a new brief with worktree path and branch, rerun `verify-stack` if it applied, regenerate the review file and dispatch `reviewer` again.
   - Allow at most 2 fix rounds in total. Fix rounds caused by `verify-stack` and by the reviewer count against the same cap. When the cap is reached and `verify-stack` still fails or the verdict is still `CHANGES_REQUESTED`, stop and escalate to the user with the open findings.

8. Dispatch `docs-writer`.
   - Brief: the issue number, the Docs to update section, the implementer's and reviewer's reports, the `verify-stack` result, the planner's AI_LOG row draft, the `AGENTS.md` path when the worktree lacks one and the decisions that bind teammates.
   - It edits the docs in the worktree and returns the PR description and the AI_LOG row.
   - Commit its doc edits on the branch if the implementer's commit does not include them. Add the AI_LOG row to `docs/AI_LOG.md` in the same PR.

9. Hand over a draft.
   - Give the user the branch name, the worktree path, the commit list, the PR description and the AI_LOG row.
   - List the decisions that bind teammates in the PR description, flagged for team discussion.
   - The PR is a draft. Its title is one imperative English sentence of 3 to 8 words, and its description is Polish with `Closes #N` first.
   - A stacked branch's PR stays a draft until its parent merges, and its description names the parent branch.
   - Push, `gh pr create` and the `ai-assisted` label happen only on the user's explicit instruction.
