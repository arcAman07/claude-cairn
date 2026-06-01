---
description: Delete a Cairn note and its index entry. Previews first; requires confirmation.
argument-hint: <name> [--yes]
allowed-tools: Bash
model: inherit
---

# Cairn rm: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" rm $ARGUMENTS
```

Interpret the output above:

- If it says **"Would delete: …"** (a dry-run preview), this is a destructive
  action that has NOT happened yet. Show the user what would be deleted and ask
  them to confirm. Only if they confirm, run the deletion for real with the
  **Bash** tool:
  `python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" rm "<name>" --yes`
- If it says **"Deleted …"**, the note is gone — report that.
- If it says **"No note matches …"**, report that nothing was deleted (safe).
- If it lists multiple candidates (ambiguous), ask the user which exact note id
  they mean, then re-run with that id and `--yes`.
