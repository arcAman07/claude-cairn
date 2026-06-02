---
description: Structural diff between two Cairn notes (which sections and file pointers differ).
argument-hint: <noteA> <noteB>
allowed-tools: Bash
model: inherit
---

# Cairn diff: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" diff $ARGUMENTS
```

Summarize the comparison above: which sections and file pointers are unique to
each note, which they share, and whether the summary changed. Do not open the
referenced files. If either note name is ambiguous, ask for the exact id.
