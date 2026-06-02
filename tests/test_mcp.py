"""v1.5 — read-only MCP server: JSON-RPC handshake, tool dispatch, errors, and
the map-not-dump guarantee on cairn_load."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

# make both lib/ and mcp/ importable
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "lib"), os.path.join(ROOT, "mcp")):
    if p not in sys.path:
        sys.path.insert(0, p)

import cairn          # noqa: E402
import cairn_mcp as M  # noqa: E402


class MCPCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-mcp-")
        # seed two notes, one with a file pointer we can check is NOT dumped
        cairn.save_note(self.store, "auth-note",
                        "## Summary\nJWT work.\n\n## Files & areas to look at\n"
                        "- src/secret_impl.py — the token logic\n\n## Next step\nGo.\n",
                        session="aaaa1111-x", cwd="/proj", tags=["auth"])
        cairn.save_note(self.store, "perf-note",
                        "## Summary\nRate limiting.\n", session="bbbb2222-y",
                        cwd="/proj", tags=["perf"])

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def req(self, method, params=None, rid=1):
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        return M.handle_request(msg, self.store)

    def call(self, name, arguments, rid=1):
        return self.req("tools/call", {"name": name, "arguments": arguments}, rid)

    def text_of(self, resp):
        return resp["result"]["content"][0]["text"]

    # ---- handshake --------------------------------------------------------
    def test_initialize(self):
        r = self.req("initialize", {"protocolVersion": "2025-06-18"})
        self.assertEqual(r["result"]["serverInfo"]["name"], "cairn")
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_initialize_defaults_protocol_when_absent(self):
        r = self.req("initialize", {})
        self.assertEqual(r["result"]["protocolVersion"], M.PROTOCOL_VERSION)

    def test_tools_list_has_all_six(self):
        r = self.req("tools/list")
        names = {t["name"] for t in r["result"]["tools"]}
        self.assertEqual(names, set(M.TOOL_IMPL))
        # every tool advertises an object input schema
        for t in r["result"]["tools"]:
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_ping(self):
        self.assertEqual(self.req("ping")["result"], {})

    def test_notification_returns_none(self):
        msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}  # no id
        self.assertIsNone(M.handle_request(msg, self.store))

    def test_notification_for_known_method_returns_none(self):
        # A known method with NO id is still a notification -> MUST NOT be answered.
        for method in ("tools/list", "ping", "initialize"):
            self.assertIsNone(
                M.handle_request({"jsonrpc": "2.0", "method": method}, self.store),
                "%s notification must get no response" % method)

    # ---- errors -----------------------------------------------------------
    def test_unknown_method_is_32601(self):
        self.assertEqual(self.req("no/such")["error"]["code"], -32601)

    def test_unknown_tool_is_32602(self):
        self.assertEqual(self.call("cairn_nope", {})["error"]["code"], -32602)

    def test_missing_required_arg_is_32602(self):
        self.assertEqual(self.call("cairn_find", {})["error"]["code"], -32602)
        self.assertEqual(self.call("cairn_show", {})["error"]["code"], -32602)
        self.assertEqual(self.call("cairn_load", {"names": []})["error"]["code"], -32602)

    def test_bad_n_type_is_32602(self):
        self.assertEqual(self.call("cairn_recent", {"n": "lots"})["error"]["code"], -32602)

    # ---- tool behavior ----------------------------------------------------
    def test_checkpoints_lists_both(self):
        t = self.text_of(self.call("cairn_checkpoints", {}))
        self.assertIn("auth-note", t)
        self.assertIn("perf-note", t)

    def test_find_ranks(self):
        t = self.text_of(self.call("cairn_find", {"query": "auth"}))
        self.assertIn("auth-note", t)
        self.assertNotIn("perf-note", t)

    def test_find_no_match(self):
        t = self.text_of(self.call("cairn_find", {"query": "kubernetes"}))
        self.assertIn("No notes match", t)

    def test_show_returns_body(self):
        t = self.text_of(self.call("cairn_show", {"name": "perf-note"}))
        self.assertIn("Rate limiting.", t)

    def test_recent_n(self):
        t = self.text_of(self.call("cairn_recent", {"n": 1}))
        # only one note line (the newest) -> exactly one "id:" marker
        self.assertEqual(t.count("id:"), 1)

    def test_path_returns_abs_path(self):
        t = self.text_of(self.call("cairn_path", {"name": "auth-note"}))
        self.assertTrue(t.endswith(".md"))
        self.assertTrue(os.path.isfile(t))

    def test_load_is_map_not_dump(self):
        # The note POINTS to src/secret_impl.py; load must surface the pointer
        # line but MUST NOT contain that file's contents (it never stores them).
        t = self.text_of(self.call("cairn_load", {"names": ["auth-note"]}))
        self.assertIn("src/secret_impl.py", t)          # the pointer is shown
        self.assertIn("map, not a dump", t)             # the guardrail banner
        self.assertIn("JWT work.", t)                   # distilled summary present

    # ---- transport loop ---------------------------------------------------
    def test_serve_loop_over_stdio(self):
        lines = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            "{ not json",                               # malformed -> parse error
        ])
        out = io.StringIO()
        M.serve(store=self.store, stdin=io.StringIO(lines), stdout=out)
        responses = [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]
        # initialize + tools/list + parse-error = 3 responses; the notification = 0
        self.assertEqual(len(responses), 3)
        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(responses[1]["id"], 2)
        self.assertEqual(responses[2]["error"]["code"], -32700)

    def test_selftest_passes(self):
        # the server's own in-process smoke test returns 0
        self.assertEqual(M._selftest(self.store), 0)


if __name__ == "__main__":
    unittest.main()
