<p align="center">
  <img src="assets/logo.png" alt="Claude Cairn" width="116">
</p>

<h1 align="center">Claude Cairn</h1>

<p align="center">
  Save a Claude Code session's <em>thinking</em> — what you explored, decided, and
  ruled out — as a portable note you can load into a fresh session anywhere, search, and share.
</p>

## What it is

Claude Cairn is a Claude Code plugin for **knowledge continuity, not code
management**. It distills a session's reasoning — the summary, the directions you
explored and *rejected* (with why), the decisions, open questions, a pointer-list
of files, and the next step — into a self-contained markdown note. Load that note
into a blank session in any directory or on any machine and you resume the
*thinking*, not a transcript.

## Install

Self-contained plugin — **Python 3 standard library only, no dependencies.**

**From GitHub:**

```
/plugin marketplace add arcAman07/claude-cairn
/plugin install cairn@arcAman07/claude-cairn
/reload-plugins
```

**Or run it from a local clone:**

```
git clone https://github.com/arcAman07/claude-cairn
claude --plugin-dir ./claude-cairn
```

Commands are namespaced under the plugin (`/cairn:checkpoint`, `/cairn:load`, …);
the auto-capture hook and the skill load automatically — no restart needed. To
also get bare aliases (`/checkpoint`, `/load`, `/find`, …), run
`scripts/install-aliases.sh`.

## Commands

| Command | Purpose |
|---|---|
| `/cairn:checkpoint [name]` | Distill this session's thinking into a note (auto-named if omitted). |
| `/cairn:checkpoint update <name>` | Append this session's new thinking onto an existing note. |
| `/cairn:checkpoints` | List all notes, newest first — the project's table of contents. |
| `/cairn:load <name> [name2 …]` | Resume note(s) as context: distilled thinking + file *pointers*, never file contents. |
| `/cairn:find <query>` | Ranked keyword search across note bodies and tags. |
| `/cairn:show <name>` | Preview a note in the terminal without loading it. |
| `/cairn:export <name>` | Write a clean, standalone markdown file built for sharing. |
| `/cairn:rm <name>` | Delete a note (previews first, then confirm). |

## Learn more

How capture, storage, loading, search, and export work — plus the note schema and
design principles — is in **[DESIGN.md](DESIGN.md)**.
