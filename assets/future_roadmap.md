# Cairn - Future Roadmap

In-depth backlog of additions, updates, and new commands. Grounded in the
two-layer model documented in [`notes.md`](notes.md):

- **Layer 1 - Digest** (`lib/cairn.py`): deterministic, time-scoped raw material.
- **Layer 2 - Distillation** (`commands/*.md`): the LLM that writes the note;
  this is where topic selection / summarization judgment happens.

Each item is tagged with **Effort** (S / M / L) and **Impact** (Low / Med / High),
and says which layer it touches.

---

## Shipped in v1.5 (branch `version_1.5`)

- **DONE - Priority 1: Checkpoint scope modes.** `/cairn:checkpoint full <name>`
  and the engine's `save --scope full|focused|delta`; scope recorded in
  frontmatter + index and shown in `list`/`show`.
- **DONE - Priority 2 commands:** `rename`, `tag`, `pin`/`unpin`, `recent`,
  `merge` (deterministic structural merge), `diff` (structural compare).
- **DONE - Priority 6: read-only MCP server** (`mcp/cairn_mcp.py`): JSON-RPC over
  stdio exposing `cairn_checkpoints`/`find`/`show`/`load`/`recent`/`path`.
- **DONE - Priority 7 (partial):** `scope`/`pinned` in frontmatter + index entries
  (backward compatible, no schema bump).

Still open below: `diff`/`merge` polish, the remaining Priority 2 items not yet
built (e.g. `graph`), Priorities 3-6 non-MCP work, and the rest of Priority 7.

---

## Priority 1 - Checkpoint *scope modes* (the Layer 2 flexibility)  [DONE in v1.5]

**Problem.** Today a second checkpoint has only two behaviors, and the most
useful one is missing:

| Behavior | How to get it now | Limitation |
|---|---|---|
| "Just the current topic" | `/checkpoint <name>` (fresh) | implicit - relies on LLM judgment, not user-controllable |
| "Only the delta since last checkpoint" | `/checkpoint update <name>` | excludes everything before the previous checkpoint |
| **"The ENTIRE list of topics in the chat, summarized as a structured TOC"** | **- not available -** | the gap |

A fresh checkpoint *could* produce the all-topics summary (its raw material is
the whole session - see the proof in `notes.md`), but Layer 2 currently scopes
the note down to the salient topic. We want to make scope an **explicit,
user-chosen command**, not a judgment call.

**Proposed surface - a `--scope` flag (with subcommand sugar):**

```
/checkpoint <name> --scope focused   # default today: the current working thread only
/checkpoint <name> --scope full      # NEW: enumerate & summarize EVERY topic in the
                                      #      whole session as a structured table of
                                      #      contents - drop nothing
/checkpoint <name> --scope delta      # == today's `update` semantics (since last note)

# sugar:
/checkpoint full <name>     →  --scope full
/checkpoint update <name>   →  --scope delta   (keep the familiar word)
```

**What changes per layer:**

- **Layer 1 (engine, `lib/cairn.py`):**
  - `focused` and `full` → whole-session digest (no `--since`). Already supported.
  - `delta` → `digest --since <last_timestamp>`. Already supported.
  - Add a small `--scope` passthrough so the engine can stamp the chosen mode
    into note frontmatter (`scope: full|focused|delta`) for later display/filtering.
    **Effort S.**
- **Layer 2 (prompt, `commands/checkpoint.md`):** add three explicit branches -
  - `focused`: "Scope the note to the current working thread; summarize earlier
     topics in one line only if they're load-bearing for the current one."
  - `full`: "Enumerate **every distinct topic/thread** discussed this session.
     Produce a `## Topics` table of contents, then one short distilled block per
     topic (Summary / Decisions / Open questions / Next step). **Drop nothing.**"
  - `delta`: "Only the material after the previous checkpoint; append as `## Update`."
  - **Effort M. Impact High.** This is the headline user request.

**Acceptance:** in a 3-topic session, `--scope full` yields a note whose
`## Topics` lists all three with a per-topic summary; `--scope focused` yields
only the last; `--scope delta` yields only post-checkpoint material. Verified by
loading each and diffing topic coverage.

---

## Priority 2 - More note-management commands

| Command | What it does | Layer | Effort | Impact |
|---|---|---|---|---|
| `/cairn:rename <old> <new>` | Rename a note (and its id slug) without losing history | 1 | S | Med |
| `/cairn:diff <a> <b>` | Show what changed/decided between two notes (or two updates of one) | 2 | M | High |
| `/cairn:merge <a> <b> … --name <new>` | Distill several notes into one consolidated note (dedupe pointers, reconcile decisions) | 2 | M | High |
| `/cairn:tag <name> [+tag …] [-tag …]` | Add/remove tags after the fact | 1 | S | Low |
| `/cairn:open <name>` | Open the note's "Files & areas" pointers in the editor (explicit opt-in to the dump) | 1 | S | Med |
| `/cairn:graph` | Render the parent/child lineage of notes (`parent` field already exists) as a tree | 1 | M | Med |
| `/cairn:recent [n]` | Last *n* notes across all projects, with one-line summaries | 1 | S | Low |
| `/cairn:pin <name>` / `unpin` | Pin notes so they sort to the top of `checkpoints` | 1 | S | Low |

---

## Priority 3 - Distillation (Layer 2) quality

- **Per-section budgets.** Let `full` mode cap each topic block so a 10-topic
  session doesn't blow up; mark dropped detail explicitly (no silent truncation).
  **Effort M. Impact Med.**
- **Rejected-direction enforcement.** Make the "Directions explored (incl.
  rejected + reason)" section a hard requirement the distill step self-checks
  before saving - the rejected paths are the highest-value, most-often-dropped
  content. **Effort S. Impact High.**
- **"What changed since last load" framing on `load`.** When loading a note that
  has `## Update` sections, surface them as a changelog rather than a flat body.
  **Effort M. Impact Med.**
- **Confidence / staleness hints.** Note records `last_timestamp`; `load` could
  warn "this note is N days old; files may have moved." **Effort S. Impact Low.**

---

## Priority 4 - Capture & automation (hooks)

- **SessionStart auto-load (ship-enabled).** Currently shipped **disabled**
  (`hooks/session_start_autoload.py`, v1.5). Finish + enable behind a config flag:
  offer the most recent note for the cwd as resumable context at session start.
  **Effort M. Impact High.**
- **PreCompact → real digest.** Today PreCompact writes a raw, un-distilled
  `source:auto` note + a `.pending-digest.txt` (a hook can't call the LLM).
  Add a follow-up that, on the next interactive turn, offers
  `/cairn:checkpoint update` to distill the pending capture. **Effort M.**
- **Idempotent auto-notes.** Keep one rolling auto-note per session (already the
  design); add a cap + rotation so long sessions don't accrete many. **Effort S.**

---

## Priority 5 - Sharing, export, portability

- **`/cairn:export --bundle`** - export a note *plus* its lineage (parents +
  updates) as one self-contained markdown file. **Effort M. Impact Med.**
- **Export formats.** `--format html|pdf` for sharing outside a terminal.
  **Effort M. Impact Low.**
- **Import.** `/cairn:import <file.md>` to bring an exported note into another
  machine's store (round-trips with export). **Effort S. Impact Med.**
- **Redaction report.** On export, print a summary of what was redacted so the
  user can review before sharing (notes are "shareable-with-review", not
  guaranteed clean). **Effort S. Impact Med.**

---

## Priority 6 - Cross-surface / integration

- **MCP server.** Expose `find` / `load` / `checkpoints` as MCP tools so notes
  are reachable from the desktop app, web, and IDE extensions - not just the CLI.
  **Effort L. Impact High.**
- **`--project` everywhere.** `find`/`list`/`load` already record origin `cwd`;
  make `--project` filtering first-class and discoverable. **Effort S.**
- **Full-text index.** Replace linear keyword scan with a small inverted index
  in `index.json` for fast `find` across hundreds of notes. **Effort M. Impact Med.**

---

## Priority 7 - Engine / robustness

- **`scope` in frontmatter + `index.json`** (see Priority 1) so `checkpoints`
  can show/filter by scope. **Effort S.**
- **Index schema migration path.** `schema_version` exists; add an explicit
  migrate-on-read step for forward compatibility. **Effort S.**
- **Streaming guarantees for very large transcripts.** Already streams
  line-by-line; add a regression fixture (40 MB+) to CI to lock it in.
  **Effort S.**
- **Better collision handling for identical note names across sessions.**
  Today the id is collision-proof; surface a friendly disambiguation in `load`
  when two notes share a human name. **Effort S.**

---

## Suggested sequencing

1. **Priority 1** (scope modes) - directly closes the documented gap; highest user value.
2. **Priority 2** `diff` + `merge` - the natural companions once multi-topic and
   multi-note workflows exist.
3. **Priority 4** SessionStart auto-load - turns Cairn from "remember to
   checkpoint" into "continuity is automatic."
4. **Priority 6** MCP - unlocks the other Claude surfaces.
5. Everything else as polish.

> See [`notes.md`](notes.md) for the mechanism these features build on, and
> `DESIGN.md` for the original architecture and the map-not-dump guarantees.
