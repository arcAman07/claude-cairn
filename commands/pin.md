---
description: Pin a Cairn note so it sorts to the top of /cairn:checkpoints and /cairn:recent.
argument-hint: <name> [--id <id>]
allowed-tools: Bash
model: inherit
---

# Cairn pin: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" pin $ARGUMENTS
```

Relay the result above. To remove a pin later, use `/cairn:unpin <name>`. If the
name is ambiguous, ask for the note id and re-run with `--id <id>`.
