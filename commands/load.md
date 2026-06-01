---
description: Load one or more Cairn notes into this session as resumed context — distilled thinking + file pointers, never file contents.
argument-hint: <name> [name2 …]
allowed-tools: Bash
model: inherit
---

# Cairn load: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" load $ARGUMENTS
```

The note(s) above are now your **resumed working context** — distilled thinking
plus a POINTER LIST of files. Treat them as where the prior session(s) left off.

**Map, not dump.** What you just loaded contains *pointers* to files, never their
contents. Do NOT open those files now. Read a specific referenced file only if
the user's current task actually requires it — on demand, one at a time.

Then briefly tell the user: which note(s) you loaded, the current state, and the
"Next step" you're resuming from. If a name was skipped (not found), say so.

(Tip: note names with spaces should be quoted; kebab-case names load cleanest
when loading several at once.)
