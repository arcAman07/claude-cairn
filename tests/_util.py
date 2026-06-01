"""Shared test helpers: synthetic transcript builder + path setup.

We deliberately do NOT commit real transcripts (they contain personal data).
Synthetic JSONL fixtures reproduce every structural case the parser must handle:
empty thinking blocks, compaction boundaries, sidechains, meta lines, list-type
tool_result content, and secrets to redact.
"""
import json
import os
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import cairn  # noqa: E402


def _line(**kw):
    return json.dumps(kw)


def assistant_text(text, ts, model="claude-opus-4-8", sidechain=False):
    return _line(type="assistant", timestamp=ts, isSidechain=sidechain,
                 message={"role": "assistant", "model": model,
                          "content": [{"type": "text", "text": text}]})


def assistant_thinking(thinking_text, ts):
    # Real transcripts always store thinking as "" on disk; we put text here to
    # PROVE the digest ignores it regardless.
    return _line(type="assistant", timestamp=ts, isSidechain=False,
                 message={"role": "assistant", "model": "claude-opus-4-8",
                          "content": [{"type": "thinking", "thinking": thinking_text,
                                       "signature": "abc"}]})


def assistant_tool(name, inp, ts, sidechain=False):
    return _line(type="assistant", timestamp=ts, isSidechain=sidechain,
                 message={"role": "assistant", "model": "claude-opus-4-8",
                          "content": [{"type": "tool_use", "id": "t1", "name": name,
                                       "input": inp, "caller": {"type": "direct"}}]})


def user_text(text, ts, meta=False):
    return _line(type="user", timestamp=ts, isMeta=meta, isSidechain=False,
                 message={"role": "user", "content": text})


def user_tool_result(content, ts, is_error=False):
    return _line(type="user", timestamp=ts, isSidechain=False,
                 message={"role": "user",
                          "content": [{"type": "tool_result", "tool_use_id": "t1",
                                       "content": content, "is_error": is_error}]})


def compaction(ts, trigger="auto", pre=200000, post=8000):
    return _line(type="system", subtype="compact_boundary",
                 content="Conversation compacted", timestamp=ts,
                 logicalParentUuid="x",
                 compactMetadata={"trigger": trigger, "preTokens": pre,
                                  "postTokens": post, "durationMs": 1000,
                                  "preCompactDiscoveredTools": ["Bash"]})


def noise(ts):
    # line types the parser must ignore without crashing
    return "\n".join([
        _line(type="file-history-snapshot", messageId="m", snapshot={}),
        _line(type="mode", mode="normal", sessionId="s"),
        _line(type="permission-mode", permissionMode="default", sessionId="s"),
        _line(type="ai-title", aiTitle="t", sessionId="s"),
        "",                       # blank line
        "{ not valid json",       # malformed line
    ])


def write_transcript(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def run_cli(argv, stdin_text=None):
    """Invoke cairn.main(argv) capturing stdout; returns (code, stdout)."""
    import io
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdout = io.StringIO()
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        code = cairn.main(argv)
        return code, sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_in, old_out
