---
description: Rename a Cairn note's display name. The note id and history are preserved.
argument-hint: <name> <new-name> [--id <id>]
allowed-tools: Bash
model: inherit
---

# Cairn rename: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" rename $ARGUMENTS
```

Relay the result above. If it says "Renamed ...", confirm the new name. If it
says "No note matches ...", report that nothing changed (safe). If it lists
several candidates (the name is ambiguous), ask the user which note id they mean,
then re-run with `--id <id>`.
