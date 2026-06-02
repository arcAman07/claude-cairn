---
description: Distill this session's thinking into a portable Cairn note (capture decisions and the directions you explored AND rejected). Use "update <name>" to append new thinking, or "full <name>" to summarize EVERY topic from the whole session.
argument-hint: [name] | full <name> | update <name>
allowed-tools: Bash, Read, Write
model: inherit
---

# Cairn checkpoint

You are capturing this session's **thinking** — not a transcript replay — into a
portable markdown note via the Cairn CLI. The note is what you'd hand a teammate
so they could resume your reasoning in a fresh session anywhere.

Arguments: `$ARGUMENTS`

`CAIRN="${CLAUDE_PLUGIN_ROOT}/lib/cairn.py"` (run it with `python3 "$CAIRN" …`).

## Step 1 — Locate THIS session's transcript
Claude Code exposes the current session id as `$CLAUDE_CODE_SESSION_ID`. Resolve by
it — this targets THIS session reliably even when several sessions share the
directory (resolving by cwd alone would pick the most-recently-written one, which
may be a different session):
```
SESSION="$CLAUDE_CODE_SESSION_ID"
python3 "$CAIRN" resolve --session "$SESSION" --cwd "$PWD"
```
That prints the transcript `.jsonl` path (call it `TRANSCRIPT`). If it fails, tell
the user no transcript was found and stop. The transcript is written incrementally,
so it already contains everything up to the previous turn; combine it with your
live memory of the current turn.

## Step 2 — Decide: new note, update, or full?
Parse the FIRST word of `$ARGUMENTS` for an optional mode keyword:
- `update <name>` → an **update**: append only the NEW thinking to an existing
  note. The name is the rest of the argument (e.g. `update auth refactor` → name
  `auth refactor`). Go to **Update flow**.
- `full <name>` → a **new checkpoint** built with **`--scope full`**: summarize
  EVERY distinct topic discussed this session, not just the latest. Go to **New
  flow** and follow the **Full-scope shape** below.
- `focused <name>`, or no keyword → a **new checkpoint** with the default
  **`--scope focused`**: scope the note to the current working thread. Go to
  **New flow**.

In every new-checkpoint case the note name is the remaining `$ARGUMENTS` if given,
else invent a short, specific, kebab-friendly name from the session's actual topic
(e.g. `jwt-auth-refactor`, not `checkpoint-1`). Remember the chosen scope
(`full` or `focused`) — you pass it to `save` in Step 3.

> Why this matters: a checkpoint runs in two layers. The `digest` (Step 1) hands
> you the WHOLE session regardless; YOU decide what lands in the note. `focused`
> = keep the current thread; `full` = deliberately keep every topic. See
> `assets/notes.md` for the full explanation.

## New flow
1. Get the reconstructed reasoning trace from disk (already redacted):
   ```
   python3 "$CAIRN" digest "$TRANSCRIPT" --session "$SESSION" --cwd "$PWD"
   ```
   This trace is reconstructed from your prose, tool actions, results, and the
   human's instructions — including exploration from BEFORE any compaction that
   your live context has since dropped. **Claude Code does not store verbatim
   chain-of-thought**, so combine this trace with **your own live memory** of
   this session (especially recent, un-compacted reasoning and the *why* behind
   choices) to write a faithful note.
2. Write the note body to a temp file with the **Write** tool. Use the sections
   below, in this order.
   - **REQUIRED — always include:** `## Summary`, `## Files & areas to look at`,
     `## Next step`.
   - **CONDITIONAL — include ONLY when the transcript genuinely supports it,**
     never invented: `## Directions explored`, `## Decisions`,
     `## Open questions / assumptions`. Omit a conditional section entirely rather
     than padding it. Most good notes have **4–5 sections, not always six.**

   Everything you write must be **grounded in the digest / your live memory of
   this session — NO hallucination.** If you're unsure something happened, leave
   it out.

   ```
   ## Summary                         (required)
   2–4 sentences: where the work stands (what's done vs not) and the goal.

   ## Directions explored             (conditional — only if real alternatives were weighed)
   Options you genuinely considered. For each REJECTED one give (a) the approach
   in a clause, (b) the concrete reason it failed, (c) the evidence that forced
   the call. Mark the chosen one. This is Cairn's highest-value section — it
   stops the next session re-litigating settled questions.
     - GOOD: "Derive the transcript path from the dir slug — rejected: long paths
       get truncated+hash-suffixed (3/26 real dirs); switched to glob-by-session-id."
     - BAD: "Considered slug resolution, rejected as unreliable." (no evidence)
   If no real alternatives were weighed (a linear task), OMIT this section.

   ## Decisions                       (conditional — if commitments were made)
   The commitments and the TRADE-OFF accepted for each — NOT a re-list of the
   options (those live in Directions). Pattern: "Chose X, accepting Y, because Z."

   ## Open questions / assumptions    (conditional — only if any are genuinely open)
   Anything unresolved, assumed, or risky the next session must know. Omit if none.

   ## Files & areas to look at        (REQUIRED)
   The map for further exploration: a POINTER LIST of the files / modules / areas
   this session touched or that the next session will need, each with one line on
   WHY it matters. Pointers ONLY — never paste file contents; the next session
   opens these on demand to pull in whatever external context it needs. Ground
   them in the digest's "File & area references" — do NOT invent paths. A path
   with no reason is noise. Prefer repo-relative paths; a machine-local/home path
   (e.g. ~/.claude/...) is a dead link elsewhere. If the session genuinely touched
   no files (a pure discussion), say so in one line.

   ## Next step                       (required)
   ONE concrete action: which file, which function, what to change — startable
   without re-reading the transcript. Not "continue the work". If the work is
   genuinely finished, say so.
   ```
   Keep the note TIGHT — aim for roughly **150–400 words** of prose (the pointer
   list can be longer; it's cheap and high-value). If a prose section runs long,
   that detail belongs in the referenced files, not the note. A vague note is
   worse than none; invent nothing not supported by the trace or memory.

   **OMIT means leave the whole header out — do NOT write a "(none)" placeholder.**
   A trivial session's note is just the three required sections, e.g.:
   ```
   ## Summary
   Fixed a typo in the README title ("Instalation" → "Installation").

   ## Files & areas to look at
   - README.md — the heading that was corrected.

   ## Next step
   None — change is complete.
   ```
   (No Directions/Decisions/Open-questions headers at all, because nothing real
   would go in them.)

   **Full-scope shape (ONLY when the mode is `full`):** instead of one focused
   note, open with a `## Topics` table of contents listing EVERY distinct thread
   this session touched, then give each topic its own short distilled block (a
   one-line summary plus its decisions / open questions / next step where real).
   Drop nothing — a `full` note is a complete map of the session, not just the
   last thing discussed. Keep each block tight (depth belongs in the referenced
   files). The required `## Summary`, `## Files & areas to look at`, and
   `## Next step` still frame the whole note.
3. Save it (the CLI adds frontmatter + updates the index). Pass the scope you
   chose in Step 2 (`full` or `focused`):
   ```
   python3 "$CAIRN" save --name "<name>" --session "<SESSION>" --cwd "$PWD" \
     --scope <full|focused> --tags "<comma,separated,topic,tags>" --body-file <tempfile>
   ```
4. Delete the temp file. Report the saved note path the CLI printed, and a
   one-line summary of what you captured.

## Update flow
1. Find the existing note and its last checkpoint time:
   ```
   python3 "$CAIRN" show "<name>"      # confirm it exists; note its content
   ```
   Read its `last_timestamp` (or `updated`) — call it `SINCE`.
2. Get only the NEW thinking since then:
   ```
   python3 "$CAIRN" digest "$TRANSCRIPT" --session "$SESSION" --cwd "$PWD" --since "<SINCE>"
   ```
3. Write a **delta** to a temp file. Lead with a one-line **`**Now:** <current
   true state in a sentence>`** so the latest truth is findable without reading
   the whole note (this becomes the note's refreshed summary). Then add only
   what's NEW or CHANGED since the last checkpoint, in the same six-section shape
   (omit sections with nothing new). Do NOT repeat content already in the note.
   If an update REVERSES an earlier decision, say so explicitly ("supersedes:
   …") so the note doesn't read as self-contradictory.
4. Append it:
   ```
   python3 "$CAIRN" save --name "<name>" --update \
     --last-timestamp "<latest event timestamp>" --body-file <tempfile>
   ```
5. Delete the temp file and report what you appended.

## Always
- The digest is pre-redacted, but still avoid writing any secret into the note.
- Capture the *why*, and especially the **rejected** directions — recovering
  those is the whole point of Cairn.
