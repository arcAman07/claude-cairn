---
description: Merge several Cairn notes into one consolidated note (deduped pointers, union tags).
argument-hint: --name <new-name> <note1> <note2> [...]
allowed-tools: Bash
model: inherit
---

# Cairn merge: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" merge $ARGUMENTS
```

Relay the result above. The merge is structural and deterministic: each source's
sections are preserved under a `From "<name>"` block, the file pointers are
unioned and de-duplicated, the tags are combined, and the new note's `parent` is
set to the first source. If a source is missing or its name is ambiguous, report
that and re-run with the exact names or ids.
