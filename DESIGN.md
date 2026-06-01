<p align="center">
  <img src="assets/logo.svg" alt="Claude Cairn" width="96">
</p>

# Claude Cairn — Design

Cairn is a Claude Code plugin for **knowledge continuity**: it turns a session's
*thinking* into a portable, human-readable note you can resume anywhere. This
document explains the problem it solves, the principles behind it, how each
operation works, the note format, and how it grows toward "invisible" continuity.

> A cairn is a stack of stones left to mark a trail through terrain that has no
> path. Cairn does the same for a project: you leave markers — distilled notes of
> what you explored, decided, and ruled out — so the next session, or the next
> person, finds the way.

## The problem

Every Claude Code session starts from a blank slate. On a small task that's fine;
on a large, long-running project it's the dominant failure mode:

- The **reasoning** behind the current state lives only in a transcript that gets
  compacted away or abandoned when the session ends.
- The **directions you explored and rejected** — often the most valuable context —
  are lost entirely, so future sessions re-litigate settled questions or re-walk
  dead ends.
- Native `/resume` only replays *one session's transcript*, locked to where it
  ran. You can't choose what carries over, can't copy it cleanly, and can't move
  it to another directory, machine, or teammate.

Cairn closes that gap: it captures the reasoning as a portable note you control.

## What it is — and isn't

Cairn distills a session's thinking into a self-contained markdown note: a
summary, the directions explored **and rejected** (with the *why*), the decisions,
open questions, a pointer-list of relevant files, and the single next step. You
can load a note into a fresh session anywhere, search across all notes, and export
one as a clean standalone document for a collaborator.

It is **knowledge continuity, not code management.** Cairn deliberately does *not*
track git state, code diffs, or file hashes. It captures and moves *context as
ideas*.

## Design principles

1. **Capture the thinking, not the transcript.** A note is the summary you'd hand
   a new teammate — including the *why* and the dropped directions — not a replay
   of messages.
2. **Read the full transcript on disk, not just the live window.** The on-disk
   JSONL transcript contains exploration the live context has already compacted
   away. That hidden detail is the most valuable thing to capture.
3. **Map, never dump.** Loading a note injects the distilled thinking plus a
   *pointer list* of files — never file contents. The session reads files on
   demand. This keeps a load cheap and lets you stitch several notes together
   without re-flooding context.
4. **Free by omission.** A fresh session starts blank and loads only what you
   choose. Unwanted context is "freed" simply by never loading it.
5. **Portable by nature.** Every note is a self-contained markdown file. Copy it
   anywhere — across directories, machines, and people — and it works.
6. **The distillation is the product.** The plumbing is easy; a vague note is
   worse than none, because the next session acts on it confidently. Most of the
   engineering effort lives in the summarization template and note structure.

## How it works

Cairn splits cleanly into a deterministic engine and the LLM's judgment. The
engine (`lib/cairn.py`, Python 3 standard library only) does all the mechanical
work — transcript resolution and parsing, redaction, the note store, listing and
search. The actual **distillation** — turning a raw reasoning trace into a good
note — is Claude's job, driven by the prompts in `commands/`.

### Capturing

When you run `/cairn:checkpoint`, the skill resolves this session's
`transcript_path`, opens the JSONL transcript from disk, and builds a *digest* —
a reconstructed, chronological reasoning trace. Because it reads the full
transcript, it recovers exploration the live window may have already lost. Claude
then folds in its own live, un-compacted memory and writes the note.

**One honest detail:** Claude Code does **not** persist verbatim
chain-of-thought to disk — the transcript's `thinking` blocks are always empty
(verified across many real transcripts). So Cairn *reconstructs* the reasoning
from what *is* on disk: the prose Claude wrote, the tool actions it took, their
results, and your instructions. It does not promise to recover hidden thoughts it
never had access to; it captures the real, recoverable signal well.

### Storing

Plain files, no database:

```
~/.claude/cairn/
  notes/
    auth-approach--20260601T143000Z--eb5b0174.md
    data-model-options--20260528T091500Z--a91c0d2e.md
  index.json          # derived cache that powers list + search
```

Each note is human-readable markdown with a small YAML frontmatter block. The
`index.json` is a *derived cache* — the notes are the source of truth, so it is
written atomically under an advisory lock and is rebuilt automatically
(`cairn.py reindex`) if it is ever lost or corrupted. The store lives at
`~/.claude/cairn` by default; override it with the `CAIRN_HOME` environment
variable (e.g. a per-repo store) or the `--store` flag. A single global store is
what lets `/cairn:load` work from any directory.

### Loading

`/cairn:load <name>` injects the note's distilled thinking plus its pointer list
into the session, so you resume the *thinking*, not the transcript. It never dumps
file contents — the engine only ever reads notes from the store, so file bodies
cannot leak through a load. Claude reads a referenced file only on demand, if the
current task needs it. A load can be re-run mid-session as a refresh, and several
notes can be loaded at once.

### Searching

`/cairn:find <query>` scans note bodies and tags and returns ranked matches with
their one-line summaries, so you can locate a past decision across dozens of
sessions. Matches in a note's name, tags, and summary are weighted above matches
in the body.

### Sharing

`/cairn:export <name>` flattens a note into one clean markdown file a teammate can
read with zero prior context — it keeps the title, date, tags, and distilled body
and strips internal bookkeeping (ids, session, index data). It's the
"onboarding-to-a-thread" document.

## The note schema

A note is YAML frontmatter followed by a stable set of sections. **Three are
always present — `## Summary`, `## Files & areas to look at`, `## Next step` —**
and three are **conditional**: `## Directions explored`, `## Decisions`, and
`## Open questions / assumptions` appear only when the session genuinely has that
content (a trivial fix is just the three required sections; a rich design session
has all six). Sections are never padded with placeholder text, and the ordering is
stable, so `/cairn:checkpoint update` produces clean, diff-friendly appends.

```markdown
---
id: auth-approach--20260601T143000Z--eb5b0174
name: auth-approach
created: 2026-06-01T14:30:00.000Z
updated: 2026-06-01T14:30:00.000Z
session_id: eb5b0174-0555-4601-804e-672d68069c89
cwd: /Users/you/project
tags: [auth, architecture, decision]
parent: null            # optional: id of a predecessor note (lineage)
source: manual          # "manual" or "auto" (PreCompact capture)
summary: One-line description used by list + search.
last_timestamp: 2026-06-01T14:30:00.000Z   # newest event captured (for incremental updates)
---

## Summary                         (required)
Where the work stands and the goal, in 2–4 sentences.

## Directions explored             (conditional)
The highest-value section when present. For each meaningful approach: what it was,
and — if rejected — the concrete reason and the evidence that forced the call, so a
future session doesn't re-walk it. The chosen direction is marked. Omitted entirely
for a linear task with no real alternatives.

## Decisions                       (conditional)
The commitments made and the trade-off accepted for each.

## Open questions / assumptions    (conditional)
What's unresolved, assumed, or risky. Omitted if there's nothing genuinely open.

## Files & areas to look at         (required)
The map for further exploration: a pointer list — paths/modules/areas, each with
one line on why it matters. Pointers only; never file contents. The next session
opens these on demand to pull in whatever external context it needs.

## Next step                       (required)
The single most obvious next action, with enough detail to start without
re-reading the transcript.
```

## Auto-capture before compaction

A `PreCompact` hook writes a **raw, mechanical** note (`source: auto`) right before
Claude Code compacts context, and stages a full digest beside it
(`<note>.pending-digest.txt`). A hook can't invoke the LLM, so this capture is
un-distilled — but it guarantees exploration is never silently lost. Refine it
later with `/cairn:checkpoint update <name>`. The hook is defensive: it always
exits 0 and never blocks or crashes a session.

## Redaction

Before a note is written, its text passes through a conservative, ReDoS-safe
secret-redactor (API-key formats, tokens, PEM blocks, `key = value` /
`"key": "value"` assignments, and passwords inside connection strings →
`[REDACTED:…]`), and oversized tool outputs are truncated. Redaction happens
*before* truncation so a secret can't survive as a fragment. An assignment is
redacted only when **both** the key names a secret **and** the value *looks* like
one (opaque, no spaces) — so an ordinary sentence quoted after a word like
`token:` is never destroyed. This is **best-effort**, not a guarantee — review a
note before sharing it.

## Seamless continuity — three tiers

Cairn is designed so you can use the simple tier today and grow into the rest:

1. **Manual.** `/cairn:checkpoint` then `/cairn:load`. Explicit and predictable.
2. **Invisible continuity.** A `SessionStart` hook (shipped, but **disabled** by
   default at `hooks/session_start_autoload.py`) detects notes for the current
   project and suggests resuming the most recent one — low-noise, honoring
   map-not-dump. Enable it by adding it to `hooks/hooks.json`. Combined with the
   `PreCompact` auto-capture, you end a session and start the next already pointed
   back at where you left off.
3. **Cross-surface (future).** Expose the note store through a small MCP server so
   any Claude surface — Claude Code, claude.ai, desktop — can read the same notes.

## Brand palette ("Trail Clay")

The logo, the launch animation, and this document share one calm palette so the
project reads as a coherent whole.

| role | hex | use |
|---|---|---|
| paper | `#F4EEE3` | background |
| stone | `#B8A98E` | the stacked stones |
| accent | `#C2613A` | the top stone · key emphasis |
| ink | `#2B2622` | text and outlines (warm near-black) |

Supporting shades, used sparingly: stone-dark `#9C8C72` (depth), panel `#EBE3D4`
(cards), muted-ink `#6B6256` (secondary text), accent-dark `#A24E2D` (depth on the
accent).
