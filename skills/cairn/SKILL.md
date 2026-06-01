---
name: cairn
description: Use when the user wants to capture, save, resume, search, relocate, or hand off a Claude Code session's THINKING across sessions, machines, or directories — e.g. "checkpoint my context", "save where we are", "resume my last session's reasoning", "what did I explore/reject on X", "carry this context to another repo", "load my cairn note". Cairn distills reasoning (decisions + the directions explored and rejected) into portable markdown notes. NOT for git/code/diff state.
---

# Claude Cairn

Cairn turns a session's **reasoning** into portable markdown notes — summary,
the directions explored AND **rejected** (with why), decisions, open questions,
a pointer list of files, and the next step — that load into a fresh session
anywhere. It is knowledge continuity, **not** code/git tracking.

When the user wants to save, resume, search, or share session context, use these
slash commands (don't reimplement them):

- `/cairn:checkpoint [name]` — distill THIS session into a note. `/cairn:checkpoint update <name>` appends new thinking to an existing note.
- `/cairn:checkpoints` — list all notes (newest first).
- `/cairn:find <query>` — ranked search over note bodies + tags.
- `/cairn:load <name> [name2 …]` — resume note(s) as working context. Map, not dump: you get distilled thinking + file *pointers*, never file contents.
- `/cairn:show <name>` — preview a note without resuming it.
- `/cairn:export <name>` — write a clean, standalone, shareable markdown file.
- `/cairn:rm <name>` — delete a note (previews first).

Notes live in `~/.claude/cairn/` (override with the `CAIRN_HOME` env var). The
deterministic engine is `${CLAUDE_PLUGIN_ROOT}/lib/cairn.py` — run
`python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" --help` for its subcommands.

A PreCompact hook auto-captures a **raw** note (`source: auto`) right before
context compaction so exploration is never silently lost; refine one later with
`/cairn:checkpoint update <name>`.

Note: Claude Code does not persist verbatim chain-of-thought to disk, so Cairn
reconstructs reasoning from the prose you wrote, your tool actions and their
results, and the user's instructions — augmented by your live memory when you
run `/cairn:checkpoint`.
