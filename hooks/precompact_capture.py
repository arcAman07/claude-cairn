#!/usr/bin/env python3
"""Cairn PreCompact auto-capture hook.

Fires right before Claude Code compacts context. A hook cannot invoke the LLM,
so it writes a *mechanical* note (source=auto) that preserves the reasoning trace
about to drop out of the live window, and stages a full digest beside it so the
next session can distill it cleanly with `/cairn:checkpoint update`.

Contract: read JSON on stdin (session_id, transcript_path, cwd, trigger), do the
capture, and ALWAYS exit 0 — a hook must never crash or block the session.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def _capture(data):
    import cairn  # imported lazily so a bad import still exits 0

    # A real PreCompact event always supplies these. If stdin gave us neither,
    # do not guess from cwd -- stay silent (empty/garbage input -> no capture).
    if not data.get("transcript_path") and not data.get("session_id"):
        return

    session = (data.get("session_id") or "").strip()
    cwd = data.get("cwd") or os.getcwd()
    trigger = data.get("trigger") or "auto"
    transcript = cairn.resolve_transcript(
        data.get("transcript_path"), session=session or None, cwd=cwd)
    if not transcript:
        return  # nothing to capture; stay silent and exit 0

    if not session:
        session = os.path.basename(transcript)[:-len(".jsonl")]

    body, summary = cairn.build_extract(transcript, session=session, cwd=cwd)
    proj = os.path.basename(cwd.rstrip("/")) or "session"
    # No timestamp in the name -- save_note's id already carries one (avoids a
    # doubled stamp). The summary records the time span for disambiguation.
    name = "auto-%s" % cairn.slugify(proj, 40)
    summary = "[auto/%s] %s" % (trigger, summary)

    store = cairn.store_dir(None)  # CAIRN_HOME or ~/.claude/cairn

    # One ROLLING auto-note per session, refreshed atomically (handles concurrency,
    # stale/corrupt entries, and index gaps -- see cairn.roll_auto_note).
    path = cairn.roll_auto_note(store, session, name, body, summary, cwd)

    # Stage the full digest beside the note for later LLM distillation.
    try:
        digest = cairn.build_digest(transcript, session=session, cwd=cwd)
        with open(path[:-len(".md")] + ".pending-digest.txt", "w") as f:
            f.write(digest)
    except Exception:
        pass

    # stdout from a PreCompact hook is informational; keep it short.
    sys.stdout.write("Cairn auto-captured pre-compaction note: %s\n" % name)


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        _capture(data)
    except Exception:
        # Never let a capture failure surface as a hook error.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
