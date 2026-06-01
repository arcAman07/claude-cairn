---
description: Export a Cairn note to a clean, self-contained, shareable markdown file.
argument-hint: <name> [--out <path>]
allowed-tools: Bash
model: inherit
---

# Cairn export: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" export $ARGUMENTS
```

Tell the user the exact path the CLI wrote to (shown above). The exported file is
self-contained and readable by someone with **zero prior context**: it keeps the
title, date, tags, and the distilled body, and strips internal metadata (ids,
session, index bookkeeping). If they want it somewhere specific, they can pass
`--out <path>`.
