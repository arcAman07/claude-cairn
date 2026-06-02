# Launch copy

Replace `OWNER` with the GitHub org/user before posting.
**Media:** attach `assets/cairn-launch.mp4` + `assets/logo.png`.

---

## Tagline options
1. **Context, shared across sessions.**  ← chosen (used in the video)
2. Save the thinking. Resume it anywhere.
3. Checkpoint the thinking, not the transcript.
4. Portable thinking-memory for Claude Code.
5. Knowledge continuity for Claude Code.

---

## X / Twitter thread (5 posts)

**1/**
Every Claude Code session starts blank. When one ends, or its context compacts, the reasoning behind where you landed, especially the paths you explored and rejected, is gone. You restart the next one from zero. 🪨

**2/**
The catch: Claude Code never writes its chain-of-thought to disk, the transcript's thinking blocks are empty. So Cairn reconstructs the reasoning from what IS there (your prose, tool actions, results) and distills it into a portable note.

**3/**
/cairn:checkpoint distills a session's thinking, summary, the directions you explored AND rejected (with why), decisions, file pointers, next step, into one markdown note. /cairn:load resumes it in a fresh session. Map, not dump: pointers, never file contents.

**4/**
Notes are plain markdown in ~/.claude/cairn, load them in any repo, on any machine, or hand one to a teammate. /cairn:checkpoints lists them, /cairn:find searches, /cairn:export writes a clean shareable file.

**5/**
It's a Claude Code plugin, Python stdlib only, no deps. Try it locally: clone, then `claude --plugin-dir ./claude-cairn`. Code + docs → github.com/OWNER/claude-cairn, save the thinking, resume it anywhere.

**Video alt-text (current cut):**
Styled as the Claude Code interface, with prompts typed into the input box and sent up into the transcript. In one session a developer runs two unrelated threads: implementing a Transformer from scratch, and implementing a Soft Actor-Critic (SAC) agent. They run `/cairn:checkpoint transformer` and `/cairn:checkpoint sac`. Then two fresh sessions each run `/cairn:load` for one thread; the resumed context (summary + next step) is already on screen, so each continues cleanly. Ends on the Claude Cairn logo and "Context, shared across sessions."

**Prior video alt-text:**
Animation styled as a real terminal. In one Claude Code session a developer juggles two unrelated projects: adding LoRA fine-tuning to a model, and implementing a MaxEnt inverse-RL paper from scratch. They run `/cairn:checkpoint lora` and `/cairn:checkpoint inverse-rl`, each saved. The screen then splits into two terminals that each run `/cairn:load` for one project; the resumed context summary (summary plus next step) is already on screen, so work continues from there. Ends on the Claude Cairn logo and the line "Context, shared across sessions."

---

## LinkedIn post

**On long Claude Code projects, the most valuable context is the first thing you lose.**

Every session starts from a blank slate. When one ends, or its context is compacted away, the reasoning behind the current state vanishes. The worst loss is the *negative* knowledge: the approaches you explored and deliberately ruled out. The next session happily re-walks those dead ends.

There's a subtle reason it's hard to recover: Claude Code doesn't persist chain-of-thought to disk, the transcript's "thinking" is empty. So **Claude Cairn reconstructs** the reasoning from what *is* on disk (the prose, the tool actions, their results) and **distills it into a portable markdown note**: a summary, the directions explored *and rejected* with the why, the decisions, a pointer-list of files, and the next step.

`/cairn:checkpoint` captures it; `/cairn:load` resumes that thinking in a fresh session, anywhere, on any machine, or for a teammate. It's knowledge continuity, not code management.

A Claude Code plugin, Python standard-library only.
Repo: github.com/OWNER/claude-cairn
Commands: `/cairn:checkpoint` · `/cairn:load` · `/cairn:checkpoints` · `/cairn:find` · `/cairn:export`
*(Media: cairn-launch.mp4 + logo.png)*
