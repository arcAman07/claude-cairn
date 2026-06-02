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

## How it's different (handy for replies / FAQ)

Launch comments will ask "isn't this just X?". These answers are specific and defensible:

- **vs built-in Checkpointing / Rewind:** that is in-session, machine-local, unnamed code+conversation *undo*. Cairn is *named, portable* checkpoints you load by name into a different session, repo, or machine, distilled thinking, not a code time-machine.
- **vs claude-mem / Mem0 / Supermemory:** those run a service, vector DB, or external AI-compression (Node, daemons, API keys). Cairn is a single Python standard-library engine, no service, no DB, no API key, and the distillation happens inside your live Claude Code session.
- **vs claude-baton and other note plugins:** baton keeps only the "latest" checkpoint per project (no names) in SQLite. Cairn gives named, load-by-name notes in plain markdown, portable anywhere, with `/cairn:export` to share.
- **What's actually distinctive:** named + load-by-name, plain-markdown + map-not-dump pointers, a first-class "directions explored AND rejected (with why)" section, and zero dependencies.
