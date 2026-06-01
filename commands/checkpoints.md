---
description: List all Cairn notes (newest first) with title, date, tags, and one-line summary.
allowed-tools: Bash
model: inherit
---

# Cairn notes

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" list
```

Relay the list above to the user (it is already newest-first). If the store is
empty, suggest they create one with `/cairn:checkpoint` (or `/checkpoint`). Do
not open or load any note here — this is just an index. To load one into context
use `/cairn:load <name>`; to preview one use `/cairn:show <name>`.
