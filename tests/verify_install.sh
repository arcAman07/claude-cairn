#!/usr/bin/env bash
# Validate a Cairn plugin tree the way the loader / a user would: manifest,
# hooks schema, referenced scripts present + runnable, CLI healthy. This is the
# part a real session-restart exercises that headless tests cannot.
#   tests/verify_install.sh [plugin_root]     # default: repo root
set -uo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
FAIL=0
ok(){ echo "  PASS $1"; }
bad(){ echo "  FAIL $1"; FAIL=1; }

echo "Verifying Cairn plugin at: $ROOT"

# 1. plugin.json
PJ="$ROOT/.claude-plugin/plugin.json"
if [ -f "$PJ" ] && python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d.get('name')=='cairn'" "$PJ" 2>/dev/null; then
  ok "plugin.json valid and name=cairn"
else
  bad "plugin.json missing/invalid or name!=cairn"
fi

# 2. hooks.json schema + PreCompact wired
HJ="$ROOT/hooks/hooks.json"
if [ -f "$HJ" ] && python3 - "$HJ" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1]))
h=d["hooks"]["PreCompact"][0]["hooks"][0]
assert h["type"]=="command" and "precompact_capture.py" in h["command"]
PY
then ok "hooks.json valid, PreCompact -> precompact_capture.py"
else bad "hooks.json missing/invalid or PreCompact not wired"; fi

# 3. referenced scripts exist
for f in lib/cairn.py hooks/precompact_capture.py; do
  [ -f "$ROOT/$f" ] && ok "exists: $f" || bad "missing: $f"
done

# 4. command files have YAML frontmatter
for c in checkpoint checkpoints load find export show rm; do
  f="$ROOT/commands/$c.md"
  if [ -f "$f" ] && head -1 "$f" | grep -q '^---$'; then ok "command: /cairn:$c"
  else bad "command missing/no-frontmatter: $c"; fi
done

# 5. SKILL present
[ -f "$ROOT/skills/cairn/SKILL.md" ] && ok "skills/cairn/SKILL.md" || bad "SKILL.md missing"

# 6. CLI healthy
if python3 "$ROOT/lib/cairn.py" --help >/dev/null 2>&1; then ok "cairn.py --help"; else bad "cairn.py --help failed"; fi
if python3 "$ROOT/lib/cairn.py" selftest >/dev/null 2>&1; then ok "cairn.py selftest"; else bad "cairn.py selftest failed"; fi

# 7. hook runs and exits 0 on empty stdin
echo "" | python3 "$ROOT/hooks/precompact_capture.py" >/dev/null 2>&1
[ $? -eq 0 ] && ok "precompact hook exits 0 on empty stdin" || bad "precompact hook nonzero on empty stdin"

echo
if [ "$FAIL" -eq 0 ]; then echo "INSTALL OK"; else echo "INSTALL HAS FAILURES"; fi
exit $FAIL
