---
description: Unpin a Cairn note (remove its pin so it sorts by recency again).
argument-hint: <name> [--id <id>]
allowed-tools: Bash
model: inherit
---

# Cairn unpin: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" unpin $ARGUMENTS
```

Relay the result above. If the name is ambiguous, ask for the note id and re-run
with `--id <id>`.
