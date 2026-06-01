#!/usr/bin/env python3
"""Cairn SessionStart auto-load — SHIPPED DISABLED (v1.5 / opt-in).

This is NOT wired into hooks/hooks.json. SessionStart auto-injection has been
historically unreliable, and an over-eager auto-load is worse than none — so v1
keeps it off. It is included, working and conservative, for users who want
"invisible continuity".

What it does when enabled: on SessionStart it finds the most recent Cairn note
whose origin cwd matches this session's cwd and, rather than dumping the whole
note, injects a SHORT pointer suggesting the user resume it explicitly. This
keeps it low-noise and honors map-not-dump.

To enable, add this block to hooks/hooks.json (then restart Claude Code):

    "SessionStart": [
      { "matcher": "*", "hooks": [
        { "type": "command",
          "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/session_start_autoload.py\"",
          "timeout": 10 } ] } ]

Contract: read JSON on stdin (session_id, cwd, source), optionally print a
SessionStart JSON payload with hookSpecificOutput.additionalContext, ALWAYS exit 0.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def _suggestion(data):
    import cairn

    cwd = data.get("cwd") or os.getcwd()
    idx = cairn.read_index(cairn.store_dir(None))
    here = [n for n in idx["notes"] if (n.get("cwd") or "") == cwd]
    if not here:
        return None
    here = cairn._by_recency(here)
    latest = here[0]
    name = latest.get("name") or latest.get("id") or "(unnamed)"
    summary = latest.get("summary") or ""
    lines = [
        "You have %d Cairn note(s) for this project. Most recent: "
        "**%s** (%s)%s" % (len(here), name, (latest.get("updated") or "")[:10],
                           " — " + summary if summary else ""),
        "To resume that thinking, run `/cairn:load %s`. "
        "To see all, `/cairn:checkpoints`." % name,
    ]
    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        ctx = _suggestion(data)
        if ctx:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": ctx}}))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
