import html
import os
import re
import subprocess
import sys
from pathlib import Path

NAME_PATTERN = re.compile(r"map\.md|defense\.md|cards/[a-z0-9]+(-[a-z0-9]+)*\.md|prs/[0-9]+\.md")

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Notatki do nauki</title>
<style>
  body { margin: 0; background: #14161a; color: #e4e6ea; font-family: system-ui, sans-serif; font-size: 17px; line-height: 1.6; }
  nav { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 24px; border-bottom: 1px solid #2c3038; }
  nav button { font-family: inherit; font-size: 14px; color: #e4e6ea; background: #20242b; border: 1px solid #2c3038; border-radius: 6px; padding: 6px 14px; cursor: pointer; }
  nav button.active { background: #3b5bdb; border-color: #3b5bdb; }
  section { display: none; padding: 16px 24px; max-width: 1100px; }
  section.active, body.drawing section { display: block; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .pr { background: #1b1e24; border: 1px solid #2c3038; border-radius: 8px; padding: 0 16px; }
  pre.md { white-space: pre-wrap; font-family: inherit; }
  pre { background: #1b1e24; padding: 12px; border-radius: 6px; overflow-x: auto; }
  code { font-size: 14px; }
  a { color: #74c0fc; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #2c3038; padding: 4px 10px; }
</style>
</head>
<body>
<nav>
__BUTTONS__
</nav>
__SECTIONS__
<script>
  function show(id) {
    for (const section of document.querySelectorAll("section")) {
      section.classList.toggle("active", section.id === id);
    }
    for (const button of document.querySelectorAll("nav button")) {
      button.classList.toggle("active", button.dataset.tab === id);
    }
  }
  for (const button of document.querySelectorAll("nav button")) {
    button.addEventListener("click", () => show(button.dataset.tab));
  }
  const first = document.querySelector("nav button");
  if (first) show(first.dataset.tab);
</script>
<script type="module">
  import { marked } from "https://cdn.jsdelivr.net/npm/marked@14.0.0/lib/marked.esm.js";
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@12.3.0/dist/mermaid.esm.min.mjs";

  mermaid.initialize({ startOnLoad: false, theme: "dark", themeVariables: { fontSize: "14px" } });
  document.body.classList.add("drawing");
  try {
    for (const pre of document.querySelectorAll("pre.md")) {
      const rendered = document.createElement("div");
      rendered.innerHTML = marked.parse(pre.textContent);
      pre.replaceWith(rendered);
    }
    for (const code of document.querySelectorAll("code.language-mermaid")) {
      const diagram = document.createElement("div");
      diagram.className = "mermaid";
      diagram.textContent = code.textContent;
      code.parentElement.replaceWith(diagram);
    }
    await mermaid.run({ nodes: document.querySelectorAll(".mermaid") });
  } finally {
    document.body.classList.remove("drawing");
  }
</script>
</body>
</html>
"""


def refuse(message: str) -> None:
    print("REFUSED: " + message, file=sys.stderr)
    sys.exit(1)


def checkouts() -> list[Path]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], capture_output=True, text=True
    )
    if result.returncode != 0:
        refuse("cannot list git worktrees from the current directory")
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]).resolve())
    return paths


def learning_dir() -> Path:
    all_checkouts = checkouts()
    setting = os.environ.get("LEARNING_DIR")
    if setting:
        folder = Path(os.path.expanduser(setting)).resolve()
    else:
        main = all_checkouts[0]
        folder = main.parent / (main.name + "-learning")
    for checkout in all_checkouts:
        if folder == checkout or checkout in folder.parents:
            refuse(str(folder) + " is inside the repository checkout " + str(checkout))
    return folder


def note_names(folder: Path) -> list[str]:
    names = []
    for path in folder.rglob("*.md"):
        name = path.relative_to(folder).as_posix()
        if NAME_PATTERN.fullmatch(name):
            names.append(name)
    return sorted(names)


def note_block(folder: Path, name: str) -> str:
    text = (folder / name).read_text(encoding="utf-8")
    return '<pre class="md">' + html.escape(text) + "</pre>"


def pr_number(name: str) -> int:
    return int(name[len("prs/"):-len(".md")])


def build_index(folder: Path) -> None:
    names = note_names(folder)
    tabs = []
    if "map.md" in names:
        tabs.append(("map", "Mapa", note_block(folder, "map.md")))
    for name in names:
        if name.startswith("cards/"):
            slug = name[len("cards/"):-len(".md")]
            tabs.append(("card-" + slug, slug, note_block(folder, name)))
    pr_names = [name for name in names if name.startswith("prs/")]
    if pr_names:
        blocks = ""
        for name in sorted(pr_names, key=pr_number, reverse=True):
            blocks += '<div class="pr">' + note_block(folder, name) + "</div>\n"
        tabs.append(("prs", "PR-y", '<div class="grid">\n' + blocks + "</div>"))
    if "defense.md" in names:
        tabs.append(("defense", "Obrona", note_block(folder, "defense.md")))

    buttons = ""
    sections = ""
    for tab_id, label, body in tabs:
        buttons += '<button data-tab="' + tab_id + '">' + label + "</button>\n"
        sections += '<section id="' + tab_id + '">\n' + body + "\n</section>\n"
    page = PAGE.replace("__BUTTONS__", buttons).replace("__SECTIONS__", sections)
    (folder / "index.html").write_text(page, encoding="utf-8")


def usage() -> None:
    print("usage: notes.py dir | notes.py write <name>", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    args = sys.argv[1:]
    if args == ["dir"]:
        folder = learning_dir()
        print(folder)
        for name in note_names(folder):
            print(name)
    elif len(args) == 2 and args[0] == "write":
        name = args[1]
        folder = learning_dir()
        if not NAME_PATTERN.fullmatch(name):
            refuse("note name " + name + " is not allowed")
        text = sys.stdin.buffer.read().decode("utf-8")
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        build_index(folder)
        print(path)
    else:
        usage()


main()
