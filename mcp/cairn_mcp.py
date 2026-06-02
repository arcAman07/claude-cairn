#!/usr/bin/env python3
"""Claude Cairn — read-only MCP server (stdlib only).

Exposes the Cairn note store to any MCP client (the Claude desktop app, web, IDE
extensions) so a session's distilled thinking is reachable everywhere, not just
the CLI. This is the "seamless context continuity" surface: browse, search, and
RESUME notes from any tool that speaks MCP.

It is deliberately READ-ONLY — it can list/find/show/load/recent/path, but it
cannot create, edit, or delete notes. External surfaces never mutate your store.

Transport: JSON-RPC 2.0 over newline-delimited stdio (the MCP stdio transport).
stdout carries ONLY protocol messages; all diagnostics go to stderr.

The protocol core is `handle_request(obj, store) -> response|None`, a pure
function (no real stdio) so it is exhaustively unit-testable. `serve()` is the
thin stdin/stdout loop around it.

Register with:
    claude mcp add cairn -- python3 /abs/path/to/mcp/cairn_mcp.py
Honors CAIRN_HOME / --store for the note store location.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import cairn  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"          # echoed unless the client requests another
SERVER_NAME = "cairn"
SERVER_VERSION = "1.5.0"


class _BadParams(Exception):
    """Raised by a tool when its arguments are invalid -> JSON-RPC -32602."""


# --------------------------------------------------------------------------
# Tool catalog (read-only)
# --------------------------------------------------------------------------

TOOLS = [
    {
        "name": "cairn_checkpoints",
        "description": "List all Cairn notes (pinned first, then newest) with name, "
                       "date, tags, scope, and one-line summary. The project's table "
                       "of contents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string",
                            "description": "only notes whose origin cwd contains this substring"},
            },
        },
    },
    {
        "name": "cairn_find",
        "description": "Ranked keyword search across Cairn note bodies and tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "search terms"},
                "project": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "cairn_show",
        "description": "Show one Cairn note in full (its summary header + body).",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "note name or id"}},
            "required": ["name"],
        },
    },
    {
        "name": "cairn_load",
        "description": "Load one or more Cairn notes as resume context: distilled "
                       "thinking plus file POINTERS only, never file contents (map, "
                       "not dump).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"},
                          "description": "note names or ids to load"},
            },
            "required": ["names"],
        },
    },
    {
        "name": "cairn_recent",
        "description": "The N most-recent Cairn notes (pinned first).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "how many (default 10)"},
                "project": {"type": "string"},
            },
        },
    },
    {
        "name": "cairn_path",
        "description": "Print the absolute file path of a Cairn note.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "note name or id"}},
            "required": ["name"],
        },
    },
]


# --------------------------------------------------------------------------
# Tool implementations -> each returns a text string (or raises _BadParams)
# --------------------------------------------------------------------------

def _note_line(n):
    pin = "📌 " if n.get("pinned") else ""
    scope = " {%s}" % n.get("scope") if n.get("scope") else ""
    tags = " ".join("#" + t for t in cairn._safe_tags(n))
    return ("• %s%s [%s]%s %s\n    %s\n    id: %s"
            % (pin, n.get("name"), cairn._fmt_date(n.get("updated")), scope, tags,
               n.get("summary") or "", n.get("id")))


def _tool_checkpoints(store, args):
    idx = cairn.read_index(store)
    notes = idx["notes"]
    project = args.get("project")
    if project:
        notes = [n for n in notes if project in (n.get("cwd") or "")]
    notes = cairn._by_pinned_recency(notes)
    if not notes:
        return "No cairn notes yet."
    return "%d note(s):\n\n%s" % (len(notes), "\n".join(_note_line(n) for n in notes))


def _tool_find(store, args):
    query = args.get("query")
    if not query or not str(query).strip():
        raise _BadParams("'query' is required and must be non-empty")
    scored = cairn.search_notes(store, str(query), project=args.get("project"))
    if not scored:
        return "No notes match %r." % query
    lines = []
    for s, n in scored:
        lines.append("• %s [%s] (score %d)\n    %s\n    id: %s"
                     % (n.get("name"), cairn._fmt_date(n.get("updated")), s,
                        n.get("summary") or "", n.get("id")))
    return "%d match(es) for %r:\n\n%s" % (len(scored), query, "\n".join(lines))


def _tool_show(store, args):
    name = args.get("name")
    if not name:
        raise _BadParams("'name' is required")
    note, err = cairn._resolve_one(store, str(name), "show")
    if err:
        return err
    meta, body = cairn.parse_note(os.path.join(cairn.notes_dir(store), note["file"]))
    head = ["# %s" % meta.get("name"),
            "_created %s · updated %s · source %s_"
            % (meta.get("created"), meta.get("updated"), meta.get("source"))]
    if meta.get("scope"):
        head.append("_scope: %s_" % meta.get("scope"))
    return "\n".join(head) + "\n\n" + body.strip()


def _tool_load(store, args):
    names = args.get("names")
    if not isinstance(names, list) or not names:
        raise _BadParams("'names' is required and must be a non-empty array")
    text, _ = cairn.render_load(store, [str(x) for x in names])
    return text


def _tool_recent(store, args):
    n = args.get("n", 10)
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise _BadParams("'n' must be an integer")
    idx = cairn.read_index(store)
    notes = idx["notes"]
    project = args.get("project")
    if project:
        notes = [x for x in notes if project in (x.get("cwd") or "")]
    notes = cairn._by_pinned_recency(notes)[:max(1, n)]
    if not notes:
        return "No cairn notes yet."
    return "\n".join(_note_line(x) for x in notes)


def _tool_path(store, args):
    name = args.get("name")
    if not name:
        raise _BadParams("'name' is required")
    note, err = cairn._resolve_one(store, str(name), "path")
    if err:
        return err
    return os.path.join(cairn.notes_dir(store), note["file"])


TOOL_IMPL = {
    "cairn_checkpoints": _tool_checkpoints,
    "cairn_find": _tool_find,
    "cairn_show": _tool_show,
    "cairn_load": _tool_load,
    "cairn_recent": _tool_recent,
    "cairn_path": _tool_path,
}


# --------------------------------------------------------------------------
# JSON-RPC core (pure)
# --------------------------------------------------------------------------

def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": e}


def _handle_tool_call(rid, params, store):
    name = params.get("name")
    args = params.get("arguments")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _err(rid, -32602, "tool 'arguments' must be an object")
    impl = TOOL_IMPL.get(name)
    if impl is None:
        return _err(rid, -32602, "unknown tool: %r" % name)
    try:
        text = impl(store, args)
    except _BadParams as e:
        return _err(rid, -32602, str(e))
    except Exception as e:                    # tool failure -> isError result, not a crash
        return _ok(rid, {"content": [{"type": "text", "text": "error: %s" % e}],
                         "isError": True})
    return _ok(rid, {"content": [{"type": "text", "text": text}], "isError": False})


def handle_request(obj, store):
    """Dispatch one JSON-RPC message. Returns a response dict, or None for a
    notification (no `id`) / a message that needs no reply."""
    if not isinstance(obj, dict):
        return _err(None, -32600, "invalid request")
    method = obj.get("method")
    rid = obj.get("id")
    # A JSON-RPC notification (no `id`) MUST NOT receive a response — for ANY
    # method, not just unknown ones. This read-only server has no notification
    # side effects, so we simply drop them.
    if "id" not in obj:
        return None

    if method == "initialize":
        client = obj.get("params") or {}
        return _ok(rid, {
            "protocolVersion": client.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": TOOLS})
    if method == "tools/call":
        params = obj.get("params") or {}
        if not isinstance(params, dict):
            return _err(rid, -32602, "params must be an object")
        return _handle_tool_call(rid, params, store)
    # Anything else with an `id` is an unknown method (bare notifications already
    # returned None at the top).
    return _err(rid, -32601, "method not found: %s" % method)


# --------------------------------------------------------------------------
# stdio loop + entrypoint
# --------------------------------------------------------------------------

def _write(stream, obj):
    stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stream.flush()


def serve(store=None, stdin=None, stdout=None):
    store = store or cairn.store_dir(None)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            _write(stdout, _err(None, -32700, "parse error"))
            continue
        resp = handle_request(obj, store)
        if resp is not None:
            _write(stdout, resp)
    return 0


def _selftest(store):
    """In-process smoke test (no real stdio): handshake + every tool dispatches."""
    fails = []

    def check(name, cond):
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)

    print("cairn-mcp selftest")
    ini = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2025-06-18"}}, store)
    check("initialize", ini["result"]["serverInfo"]["name"] == "cairn")
    tl = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, store)
    names = {t["name"] for t in tl["result"]["tools"]}
    check("tools/list has all 6", names == set(TOOL_IMPL))
    note = handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}, store)
    check("notification -> no response", note is None)
    unk = handle_request({"jsonrpc": "2.0", "id": 4, "method": "no/such"}, store)
    check("unknown method -> -32601", unk["error"]["code"] == -32601)
    call = handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "cairn_checkpoints", "arguments": {}}}, store)
    check("tools/call dispatches", "content" in call["result"])
    print("\n%s (%d failure(s))" % ("OK" if not fails else "FAILED", len(fails)))
    return 1 if fails else 0


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="cairn-mcp",
                                description="Cairn read-only MCP server (stdio)")
    p.add_argument("--store", help="note store (default: $CAIRN_HOME or ~/.claude/cairn)")
    p.add_argument("--selftest", action="store_true", help="run an in-process smoke test")
    args = p.parse_args(argv)
    store = cairn.store_dir(args)
    if args.selftest:
        return _selftest(store)
    return serve(store=store)


if __name__ == "__main__":
    sys.exit(main())
