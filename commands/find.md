---
description: Search Cairn note bodies + tags for a query and return ranked matches with summaries.
argument-hint: <query>
allowed-tools: Bash
model: inherit
---

# Cairn find: $ARGUMENTS

```!
python3 "${CLAUDE_PLUGIN_ROOT}/lib/cairn.py" find "$ARGUMENTS"
```

Relay the ranked matches above (highest score first). Each line shows the note
name, date, and one-line summary. If there are no matches, say so plainly and
suggest broader terms. Do NOT open the matched notes' referenced files. If the
user wants to resume one, point them to `/cairn:load <name>`; to peek, `/cairn:show <name>`.
