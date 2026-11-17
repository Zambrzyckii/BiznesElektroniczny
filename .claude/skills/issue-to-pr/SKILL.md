---
name: issue-to-pr
description: Manual route from one issue to an opened PR. Creates a worktree, then runs planner, one gate only when there are questions, implementer, verify-stack, reviewer and docs-writer.
disable-model-invocation: true
argument-hint: <issue-number> [base-branch] [lokalnie]
---

# issue-to-pr

You are the controller. You run the route below for issue `$ARGUMENTS[0]`. Any later token `lokalnie` or `local` is the local flag and is never a base branch. The other later token, if any, is the base branch, or `origin/main` when there is none. You dispatch the agents in `.claude/agents/` and write no code yourself.

## Rules for the whole route

- Stop for the user in exactly two cases. The first is the gate (step 4). The second is a blocked route, which is a `BLOCKED` or `NEEDS_CONTEXT` the planner cannot resolve or the fix-round cap. Never ask anything else.
- After the gate the route runs to the end. Without the local flag it pushes and opens the PR (step 9). With the local flag it stops before the push and gives the same hand-over with the branch and the worktree instead of a link.
- Never create or edit an issue. Reading one is allowed. The one exception is adding the runner as assignee with `gh issue edit <n> --add-assignee @me`, after a yes at the gate.
- Give every dispatch the absolute worktree path, the branch name and the full issue text. A subagent starts in another checkout and its cwd resets between calls.
- A worktree branched from `origin/main` can lack `AGENTS.md` until the AI layer is merged. When it does, give every dispatch to `planner`, `implementer`, `reviewer` and `docs-writer` the absolute path of `AGENTS.md` in your own checkout as required reading.
- Run one `verify-stack` at a time and give it the absolute worktree path, so it never runs against your own checkout. Never start Docker by hand.

## Steps

1. Read the issue.
   - Run `gh issue view <n>` (read-only) or use the text the user pasted.
   - Check whether the issue is assigned to the person running the skill. `gh api user` gives the login.
   - An unassigned issue is one question at the gate (step 4), as `AGENTS.md` requires an assignee. An issue assigned to someone else means stop, because it is their issue.
   - Note the acceptance criteria. Reviewer and docs-writer need them.

2. Create the worktree.
   - Choose a branch name `<issue-number>-<short-english-slug>`.
   - Run `git fetch origin` first, unless the user said to stay offline. When offline, branch from the existing remote-tracking base branch and say so in the hand-over.
   - Run `git worktree add <path> -b <issue-number>-<slug> <base branch>` from your checkout. Put `<path>` outside the checkout, next to it.
   - The base branch defaults to `origin/main`. When the user gives another branch, this is a stacked branch (see step 9).
   - Do not rely on the agent `isolation` default. The worktree is always created here, so every agent works on a known path and branch.

3. Dispatch `planner`.
   - Brief: the issue text, the repo path to read, and the `AGENTS.md` path when the worktree lacks one.
   - The planner has no shell. Pass it the base branch and its commit, and the relevant `git log` or changed files.
   - It returns the sections Files, Steps, Acceptance checks, Verification, Docs to update, AI_LOG row draft and Open decisions.

4. Decision gate.
   - Collect everything that needs the user into one message. That is the planner's open decisions and the assignee question from step 1.
   - If there is nothing, do not stop and go to step 5.
   - Write the message in plain Polish. Ask one short question per decision, give each option a one-line trade-off and put the recommendation first. Add no plan summary and no minor findings.
   - After a yes to the assignee question, run `gh issue edit <n> --add-assignee @me`.
   - Put the answers into the brief before step 5. Anything in the planner's "Ask first" list that the user did not approve stays out of the plan.
   - Mark the answers that bind teammates, such as the settings method or the ports. They are flagged in the PR description for team discussion (steps 8 and 9).

5. Dispatch `implementer` with the approved Files and Steps.
   - The dispatch must name both the absolute worktree path and the branch name. The agent prefixes every Bash command with `cd <worktree-path> &&` and stops when `cd <worktree-path> && git branch --show-current` differs from the branch you gave.
   - Add the `AGENTS.md` path when the worktree lacks one.
   - Run several implementers in parallel only for independent issues, each in its own worktree. Steps of one plan run in order.
   - Read its report. `Status: DONE` or `DONE_WITH_CONCERNS` moves on. `NEEDS_CONTEXT` or `BLOCKED` goes back to the planner first. Only if the planner cannot resolve it, stop and tell the user in plain words what blocks. Never push past a blocked status.

6. Run `verify-stack` when the change touches `deploy/` or `shop/`.
   - Pass it the absolute worktree path. Act on its result line.
   - `VERIFY: FAIL <check>` goes to the implementer as a fix round. Rerun `verify-stack` after the fix. Do not go to step 7 while the result is `FAIL`.
   - `VERIFY: SKIPPED <reason>` is recorded in the PR description as not verified, with the reason. The PR is then a draft (step 9).

7. Dispatch `reviewer`.
   - The reviewer has only Read, Grep and Glob, so it cannot run git. Prepare its input first. From the worktree, write one file with `git log --oneline <base>..HEAD`, then `git diff --stat <base>..HEAD`, then `git diff -U10 <base>..HEAD`. Put it in a `mktemp` path, never in the worktree.
   - Dispatch with that file path, the issue's acceptance criteria, the worktree path and the `AGENTS.md` path when the worktree lacks one. Do not pass the implementer's conclusions.
   - `Verdict: APPROVE` moves on, with the minors noted.
   - `Verdict: CHANGES_REQUESTED` starts a fix round. Send the findings to `implementer` as a new brief with worktree path and branch, rerun `verify-stack` if it applied, regenerate the review file and dispatch `reviewer` again.
   - Allow at most 2 fix rounds in total. Fix rounds caused by `verify-stack` and by the reviewer count against the same cap. When the cap is reached and `verify-stack` still fails or the verdict is still `CHANGES_REQUESTED`, stop and tell the user the open findings.

8. Dispatch `docs-writer`.
   - Brief: the issue number, the Docs to update section, the implementer's and reviewer's reports, the `verify-stack` result, the planner's AI_LOG row draft, the `AGENTS.md` path when the worktree lacks one and the decisions that bind teammates.
   - Also pass "Data i autor" (the date, the user's name and GitHub login) and "Narzędzie i model" (the tool and the models that actually ran).
   - It edits the docs in the worktree and returns the PR description and the AI_LOG row.
   - Commit its doc edits on the branch if the implementer's commit does not include them. Add the AI_LOG row to `docs/AI_LOG.md` in the same PR.

9. Open the PR.
   - The PR title is one imperative English sentence of 3 to 8 words. The description is Polish with `Closes #N` first. List the decisions that bind teammates in it, flagged for team discussion.
   - Without the local flag, push with `git push -u origin <branch>`. Then run `gh pr create` with the title, the description and `--label ai-assisted`.
   - The PR is ready for review, except in two cases where it is a draft.
     - A stacked branch is a draft until its parent merges, as `CONTRIBUTING.md` requires. Run `gh pr create --draft --base <parent-branch>`, and the description names the parent branch.
     - The change touches `deploy/` or `shop/` and `verify-stack` returned `VERIFY: SKIPPED`. The draft carries the reason in one line. Untested Docker changes never go out as ready.
   - Do not wait for CI.
   - With the local flag, do not push. Give the branch name, the worktree path, the commit list, the PR description and the AI_LOG row.
   - The final message to the user has at most 5 lines. It gives the PR link, or the branch and the worktree with the local flag. It adds one sentence on what changed, what was not verified if anything and the decisions that bind teammates if any. Nothing else.
