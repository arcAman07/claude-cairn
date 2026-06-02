---
description: Show the most-recent Cairn notes (pinned first, then newest).
argument-hint: [--n N] [--project PATH]
allowed-tools: Bash
model: inherit
---

# Cairn recent: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" recent $ARGUMENTS
```

Relay the list above: pinned notes first, then newest. These are pointers, a map
and not a dump, so do not open the referenced files. To resume one, use
`/cairn:load <name>`; to see everything, `/cairn:checkpoints`.
