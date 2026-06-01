#!/usr/bin/env bash
# Install bare-name command aliases (/checkpoint, /checkpoints, /load, /find,
# /export) into ~/.claude/commands so the headline commands work without the
# `/cairn:` plugin prefix. The namespaced /cairn:* commands keep working too.
#
# These aliases bake in an ABSOLUTE path to lib/cairn.py (user-level commands
# don't get ${CLAUDE_PLUGIN_ROOT}). Usage:
#   scripts/install-aliases.sh [dest_dir]      # default: ~/.claude/commands
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/.claude/commands}"
mkdir -p "$DEST"

if [ ! -f "$PLUGIN_ROOT/lib/cairn.py" ]; then
  echo "error: $PLUGIN_ROOT/lib/cairn.py not found" >&2
  exit 1
fi

for c in checkpoint checkpoints load find export; do
  src="$PLUGIN_ROOT/commands/$c.md"
  [ -f "$src" ] || { echo "skip: $src missing" >&2; continue; }
  out="$DEST/$c.md"
  # Substitute the plugin-root placeholder with the absolute path.
  sed "s#\${CLAUDE_PLUGIN_ROOT}#$PLUGIN_ROOT#g" "$src" > "$out"
  echo "installed /$c -> $out"
done

echo
echo "Done. Bare aliases call: $PLUGIN_ROOT/lib/cairn.py"
echo "Namespaced /cairn:* commands remain available via the plugin."
echo "Note: /show and /rm stay namespaced (/cairn:show, /cairn:rm) by design."
