---
description: Add or remove tags on a Cairn note.
argument-hint: <name> [--add a,b] [--remove c]
allowed-tools: Bash
model: inherit
---

# Cairn tag: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" tag $ARGUMENTS
```

Relay the updated tag list above. With no `--add`/`--remove` this simply shows
the note's current tags. If the name is ambiguous, ask for the note id and re-run
with `--id <id>`.
