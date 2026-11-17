---
name: learning-notes
description: Writes Polish learning notes about this repo outside the repo and rebuilds their page. Use it when someone asks for learning notes, and at the end of issue-to-pr.
argument-hint: card <component> | pr <number> | map | defense
allowed-tools: Bash(python *learning-notes/notes.py*), Bash(git log *), Bash(git diff *), Bash(gh pr view *), Bash(gh pr diff *), Bash(gh issue view *)
---

# learning-notes

You write one learning note for the mode in `$ARGUMENTS`. The notes live outside the repo and a helper script writes them. With an empty or unknown mode, write `map`. Never ask the user a question.

1. Start with `python "${CLAUDE_SKILL_DIR}/notes.py" dir`. On a `REFUSED:` line stop and repeat that line. Otherwise line 1 is the notes folder and the next lines are the notes that exist.
2. Write every note with `python "${CLAUDE_SKILL_DIR}/notes.py" write <name> <<'LEARNING_NOTE_END'`, closed by `LEARNING_NOTE_END`. Never use Write or Edit for notes. On a `REFUSED:` line stop and end with that line. The helper rebuilds `index.html` after each write.
3. Sources. Read the code, `git log` and `git diff` of the current checkout. When the caller names a worktree path, read files under it and run git there as `cd <worktree> && git log ...` or `cd <worktree> && git diff ...`, never `git -C`. Write only what the code shows, cite repo-relative paths, and say plainly when something does not exist yet.
4. Language and reading level. Notes are Polish, as `CONTRIBUTING.md` requires for documentation. Names, paths and commands stay as they are. Write for a teammate who has never opened this part of the repo, in short sentences with one idea each and plain words. Explain a technical term in everyday words before naming it. One everyday comparison per idea, not more.
5. Modes.
   - `card <component>` writes `cards/<component>.md`. The component is a lowercase kebab-case name of a part that can be started, stopped or tested on its own (`scraper`, `shop`, `mailpit`). Reuse a listed card name when one fits. A card is rewritten from the code each time, with the headings `## Co robi`, `## Z czym się łączy`, `## Gdzie jest w repo`, `## Jak uruchomić, zatrzymać i podejrzeć`, `## Typowa awaria i naprawa`, `## Skąd się wziął` (issue and PR, found with `git log`) and `## Pytania na obronę`.
   - `pr <number>` writes `prs/<number>.md`, five sentences on what changed in the system and why. Read `gh pr view` and `gh pr diff`. When no such PR exists, the number is an issue number from a local run. Then read `gh issue view` and the branch's `git log` and `git diff` against the base branch the caller names, else `main`, and say in the first line that the PR is not open yet.
   - `map` writes `map.md` with one `flowchart LR` in a mermaid code block, of the components that exist now, edges labelled with what passes between them, and one line per component below it.
   - `defense` writes `defense.md`. For each listed card it gives 3 to 5 questions with a short answer hint and the file to open. A last section covers the course's live modifications, which are a broken container config, changing the free-shipping threshold and adding an E2E step for the Regulamin page, plus questions on a code fragment, a PR or an AI log entry. For each it names the file to open and the first command to run, or says the part does not exist yet.
6. End with one line naming the written note and `index.html`.
