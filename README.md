<p align="center">
  <img src="assets/logo.png" alt="Claude Cairn" width="116">
</p>

<h1 align="center">Claude Cairn</h1>

<p align="center">
  Save a Claude Code session's <em>thinking</em> (what you explored, decided, and
  ruled out) as a portable note you can load into any fresh session, search, and share.
</p>

<p align="center">
  <a href="https://github.com/arcAman07/claude-cairn/actions/workflows/test.yml"><img src="https://github.com/arcAman07/claude-cairn/actions/workflows/test.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="python 3.10+">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen.svg" alt="no dependencies">
</p>

<p align="center">
  <a href="https://github.com/arcAman07/claude-cairn/raw/main/assets/cairn-launch.mp4">
    <img src="assets/cairn-launch.gif" alt="Claude Cairn demo: two threads in one session, each checkpointed and resumed cleanly" width="760">
  </a>
</p>

<p align="center"><em>Checkpoint a session's thinking, then resume it in a fresh session anywhere. (Click the demo for the full-resolution video.)</em></p>

## What it is

Every Claude Code session starts from a blank slate. On a long project the reasoning
behind the current state, especially the directions you explored and **rejected**, is
lost when the session ends or its context compacts. Native `/resume` only replays one
transcript, locked to where it ran.

Claude Cairn is a Claude Code plugin for **knowledge continuity, not code
management**. It distills a session's reasoning into a self-contained markdown note:
a summary, the directions you explored and rejected (with the why), the decisions, a
pointer list of files, and the next step. Load that note into a blank session in any
directory or on any machine and you resume the *thinking*, not a transcript.

> One honest detail: Claude Code does not persist verbatim chain-of-thought to disk.
> So Cairn reconstructs the reasoning from what *is* on disk (the prose Claude wrote,
> the tool actions it took, their results, and your instructions) and folds in
> Claude's live memory when you checkpoint. It captures the real, recoverable signal.

## Features

- **Capture the why, including dead ends.** The note records the approaches you
  rejected and the reason, so the next session does not re-litigate settled questions.
- **Map, not dump.** Loading a note injects distilled thinking plus a pointer list of
  files, never file contents. The session reads a file only on demand.
- **Portable by nature.** Every note is one self-contained markdown file that works
  across directories, machines, and teammates.
- **Global store, load anywhere.** Notes live in `~/.claude/cairn/` so a load works
  from any directory. Override the location with `CAIRN_HOME`.
- **Auto-capture before compaction.** A `PreCompact` hook saves a raw note before
  Claude Code compacts context, so exploration is never silently lost.
- **Best-effort secret redaction.** API keys, tokens, PEM blocks, and connection
  strings are redacted before a note is written (still review before sharing).
- **Zero dependencies.** A single Python 3 standard-library engine. Nothing to install.

## Install

**From GitHub (marketplace):**

```
/plugin marketplace add arcAman07/claude-cairn
/plugin install cairn@arcAman07/claude-cairn
```

**Run a local clone for one session (no install):**

```bash
git clone https://github.com/arcAman07/claude-cairn
claude --plugin-dir ./claude-cairn
```

Commands are namespaced under the plugin (`/cairn:checkpoint`, `/cairn:load`, and so
on); the auto-capture hook and the skill load automatically. To also get bare aliases
(`/checkpoint`, `/load`, `/find`, `/checkpoints`, `/export`) in every session, run
`scripts/install-aliases.sh`.

Requires only Python 3.10 or newer (standard library only).

## Usage

A single session often drifts across **unrelated threads**. Say that in one chat you
implement a Transformer from scratch and, in the same session, a Soft Actor-Critic
(SAC) agent. When the session ends or its context compacts, both threads are gone,
and you can't split them out or continue either one later.

### 1. Checkpoint each thread before it is lost

After working through the first thread, distill it into its own note:

```text
> implement a Transformer from scratch
  ● transformer.py · multi-head attention + FFN
/cairn:checkpoint transformer
  ✓ Saved checkpoint · transformer
```

Then the second thread, into a separate note:

```text
> also: implement Soft Actor-Critic (SAC)
  ● sac.py · actor + twin critics + entropy temp
/cairn:checkpoint sac
  ✓ Saved checkpoint · sac
```

Two threads, two checkpoints, cleanly separated. Each note captures the summary, the
directions you explored **and rejected** (with the why), a pointer list of files, and
the next step, distilled from the session rather than dumped as a raw transcript.

### 2. Resume each thread in a fresh session

Later, in a new session (any directory, any machine), load just the thread you want.
The distilled thinking flows back in and you continue from the next step, never
reopening the old transcript:

```text
/cairn:load transformer
  resumed · transformer
  summary: MHA + FFN blocks, pre-norm
  next:    add positional encoding + train
```

```text
/cairn:load sac
  resumed · sac
  summary: actor + twin critics + entropy temperature
  next:    add a replay buffer + the train loop
```

Checkpoints carry your context from one session to the next, including which
approaches you rejected and why, so the new session never re-litigates settled
questions.

### 3. Everyday moves

```bash
/cairn:checkpoints                       # list all notes, newest first
/cairn:recent --n 5                      # the 5 most-recent notes (pinned first)
/cairn:find "twin critics"               # ranked search across every note body and tags
/cairn:checkpoint full ml-session        # ONE note summarizing BOTH threads as a table of contents
/cairn:merge --name ml transformer sac   # consolidate the two notes into one (deduped pointers)
/cairn:diff transformer sac              # see how the two notes differ (sections + file pointers)
/cairn:export transformer                # write a clean, shareable standalone markdown file
```

## Commands

| Command | Purpose |
|---|---|
| `/cairn:checkpoint [name]` | Distill this session's thinking into a note (auto-named if omitted). |
| `/cairn:checkpoint full <name>` | Like checkpoint, but summarize EVERY topic this session as a table of contents (not just the current thread). |
| `/cairn:checkpoint update <name>` | Append this session's new thinking onto an existing note. |
| `/cairn:checkpoints` | List all notes, newest first: the project's table of contents. |
| `/cairn:recent [--n N]` | The N most-recent notes (pinned first). |
| `/cairn:load <name> [name2 ...]` | Resume note(s) as context: distilled thinking plus file pointers, never file contents. |
| `/cairn:find <query>` | Ranked keyword search across note bodies and tags. |
| `/cairn:show <name>` | Preview a note in the terminal without loading it. |
| `/cairn:export <name>` | Write a clean, standalone markdown file built for sharing. |
| `/cairn:rename <name> <new-name>` | Rename a note (its id and history are preserved). |
| `/cairn:tag <name> [--add a,b] [--remove c]` | Add or remove tags on a note. |
| `/cairn:pin <name>` / `/cairn:unpin <name>` | Pin a note to the top of lists (or remove the pin). |
| `/cairn:merge --name <new> <a> <b> ...` | Merge several notes into one (deduped pointers, union tags). |
| `/cairn:diff <a> <b>` | Structural diff of two notes: which sections and file pointers differ. |
| `/cairn:rm <name>` | Delete a note (previews first, then confirm). |

A `PreCompact` hook also auto-captures a raw note before Claude Code compacts, so
nothing is silently lost.

### Checkpoint scope: `focused` vs `full`

A checkpoint runs in two layers: the engine's `digest` always hands Claude the
WHOLE session, and Claude decides what lands in the note. By default
(`--scope focused`) the note covers the current working thread. `/cairn:checkpoint
full <name>` (`--scope full`) instead summarizes every distinct topic from the
session as a `## Topics` table of contents, so a single note maps the whole
session. See [assets/notes.md](assets/notes.md) for the full explanation.

## MCP server (use Cairn from the desktop app, web, and IDEs)

Cairn ships a small **read-only** MCP server so your notes are reachable from any
MCP client, not just the CLI. Register it once:

```bash
claude mcp add cairn -- python3 /absolute/path/to/claude-cairn/mcp/cairn_mcp.py
```

Or add it to an `.mcp.json` the client reads:

```json
{
  "mcpServers": {
    "cairn": {
      "command": "python3",
      "args": ["/absolute/path/to/claude-cairn/mcp/cairn_mcp.py"]
    }
  }
}
```

It exposes read-only tools (`cairn_checkpoints`, `cairn_find`, `cairn_show`,
`cairn_load`, `cairn_recent`, `cairn_path`) so any surface can browse and RESUME
notes, but never create, edit, or delete them. `cairn_load` honors map-not-dump:
it returns distilled thinking plus file pointers, never file contents. The store
location follows `CAIRN_HOME` (default `~/.claude/cairn`).

## How it works

Cairn splits into a deterministic engine and the model's judgment. The engine
(`lib/cairn.py`, Python 3 standard library only) does the mechanical work: worktree
and multi-session-safe transcript resolution, a streaming digest with redaction, the
note store, and ranked search. The actual distillation, turning a reasoning trace into
a good note, is Claude's job, driven by the prompts in `commands/`. Notes are the
source of truth; `index.json` is a derived cache that rebuilds itself if lost.

Full details (the note schema, redaction, the digest, the continuity tiers) are in
**[DESIGN.md](assets/DESIGN.md)**.

## Verify it

```bash
python3 lib/cairn.py selftest      # one-command smoke test
python3 mcp/cairn_mcp.py --selftest  # MCP server smoke test
bash tests/run_tests.sh            # full unit suite (standard library only)
bash tests/verify_install.sh       # validate the plugin tree
```

181 tests, standard library only, lint-clean.

## License

MIT. See [LICENSE](LICENSE).
