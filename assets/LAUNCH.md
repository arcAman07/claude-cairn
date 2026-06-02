# Launch copy

Repo: `github.com/arcAman07/claude-cairn` (links below are set to it).
**Media:** attach `assets/cairn-launch.mp4` + `assets/logo.png`.

---

## Tagline options
1. **Context, shared across sessions.**  (chosen, used in the video)
2. Save the thinking. Resume it anywhere.
3. Checkpoint the thinking, not the transcript.
4. Portable thinking-memory for Claude Code.
5. Knowledge continuity for Claude Code.

---

## X / Twitter (main tweet + link reply)

**Tweet 1 (main, 276 chars):**
Every Claude Code session starts blank. When one ends or compacts, the reasoning behind where you landed, especially the paths you explored and rejected, is gone.

Claude Cairn checkpoints a session's thinking into a portable note you can load into a fresh session anywhere. 🪨

**Tweet 2 (reply, with the link):**
It's a Claude Code plugin, Python stdlib only, no deps.

Install:
/plugin marketplace add arcAman07/claude-cairn
/plugin install cairn@arcAman07/claude-cairn

Code + docs: github.com/arcAman07/claude-cairn

(The link lives in the reply, not the first tweet, which tends to get better reach.)

**Video alt-text (current cut):**
Styled as the Claude Code interface, with prompts typed into the input box and sent up into the transcript. In one session a developer runs two unrelated threads: implementing a Transformer from scratch, and implementing a Soft Actor-Critic (SAC) agent. They run `/cairn:checkpoint transformer` and `/cairn:checkpoint sac`. Then two fresh sessions each run `/cairn:load` for one thread; the resumed context (summary + next step) is already on screen, so each continues cleanly. Ends on the Claude Cairn logo and "Context, shared across sessions."

---

## LinkedIn post

**On long Claude Code projects, the most valuable context is the first thing you lose.**

Every session starts from a blank slate. When one ends, or its context is compacted away, the reasoning behind the current state vanishes. The worst loss is the *negative* knowledge: the approaches you explored and deliberately ruled out. The next session happily re-walks those dead ends.

There's a subtle reason it's hard to recover: Claude Code doesn't persist chain-of-thought to disk, the transcript's "thinking" is empty. So **Claude Cairn reconstructs** the reasoning from what *is* on disk (the prose, the tool actions, their results) and **distills it into a portable markdown note**: a summary, the directions explored *and rejected* with the why, the decisions, a pointer-list of files, and the next step.

`/cairn:checkpoint` captures it; `/cairn:load` resumes that thinking in a fresh session, anywhere, on any machine, or for a teammate. It's knowledge continuity, not code management.

A Claude Code plugin, Python standard-library only, no dependencies.
Repo: github.com/arcAman07/claude-cairn
Commands: `/cairn:checkpoint` · `/cairn:load` · `/cairn:checkpoints` · `/cairn:find` · `/cairn:export`
*(Media: cairn-launch.mp4 + logo.png)*

---

## Reddit (suggested: r/ClaudeAI; r/commandline or r/programming with a lighter touch)

**Title:**
I built Claude Cairn: portable "save the thinking" checkpoints for Claude Code (open source, stdlib only)

**Body:**
On long Claude Code projects I kept hitting the same wall. Every session starts from a blank slate, and when one ends or its context gets compacted, the reasoning behind where I landed is gone, especially the approaches I tried and deliberately ruled out. The next session happily re-walks those dead ends.

The annoying part is you can't just grep the transcript for it: Claude Code doesn't persist its chain-of-thought to disk. So Claude Cairn reconstructs the reasoning from what IS on disk (your prose, the tool actions, their results) and distills it into a portable markdown note: a summary, the directions explored and rejected with the why, the decisions, a pointer-list of files, and one concrete next step. It's map-not-dump, the note stores pointers to files, never their contents.

- `/cairn:checkpoint` captures the current session's thinking into a note.
- `/cairn:load` resumes it in a fresh session, in any repo, on any machine, or for a teammate.
- `/cairn:checkpoints`, `/cairn:find`, `/cairn:export` to list, search, and share.

Notes are plain markdown in `~/.claude/cairn`, so they stay yours to read and edit. It's a Claude Code plugin, Python standard library only, no dependencies, MIT licensed.

Install:

    /plugin marketplace add arcAman07/claude-cairn
    /plugin install cairn@arcAman07/claude-cairn

Repo (code, docs, and a short demo video): github.com/arcAman07/claude-cairn

Happy to answer questions, and I'd love feedback on the note format, that's the part I most want to get right.

---

## Product Hunt

**Name:** Claude Cairn

**Tagline (<= 60 chars):**
1. Context, shared across Claude Code sessions  (chosen, 45 chars)
2. Checkpoint Claude Code's thinking, resume it anywhere  (53 chars)
3. Portable memory notes for Claude Code  (37 chars)

**Description (short):**
Claude Cairn distills a Claude Code session's thinking, the summary, the directions you explored and rejected, the decisions, file pointers, and the next step, into a portable markdown note. Load it into a fresh session anywhere, search it, or hand it to a teammate. Knowledge continuity, not git.

**Topics:** Developer Tools · Artificial Intelligence · Open Source · Productivity

**Pricing:** Free, open source (MIT)

**Links:**
- Website / repo: github.com/arcAman07/claude-cairn

**Maker's first comment:**
Hey Product Hunt 👋

I built Claude Cairn to fix something that kept biting me on long Claude Code projects: every session starts from a blank slate, and when one ends or its context is compacted, the reasoning behind where you landed is gone, especially the approaches you tried and deliberately ruled out. The next session happily re-walks those dead ends.

Here's the subtle part: Claude Code doesn't persist its chain-of-thought to disk, so you can't just grep the transcript for it. Cairn reconstructs the reasoning from what IS on disk (your prose, the tool actions, their results) and distills it into a portable markdown note: a summary, the directions you explored and rejected with the why, the decisions, a pointer-list of files, and one concrete next step. Map, not dump, it stores pointers to files, never their contents.

`/cairn:checkpoint` captures it. `/cairn:load` resumes that thinking in a fresh session, in any repo, on any machine, or for a teammate. `/cairn:checkpoints`, `/cairn:find`, and `/cairn:export` list, search, and share them. Notes are plain markdown in ~/.claude/cairn, so they stay yours to read and edit.

It's a Claude Code plugin, Python standard library only, no dependencies.
Install: `/plugin marketplace add arcAman07/claude-cairn` then `/plugin install cairn@arcAman07/claude-cairn`.

Would love your feedback 🪨

**Gallery suggestions:**
- `assets/cairn-launch.mp4` (the ~44s demo) as the first gallery item.
- `assets/logo.png` as the thumbnail / icon.
- Optional: a still of a real checkpoint note and a `/cairn:load` resume in a fresh session.
