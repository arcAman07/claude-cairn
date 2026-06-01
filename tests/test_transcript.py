"""Phase 0 gates: transcript resolution + digest parsing/budgeting."""
import glob
import os
import tempfile
import time
import unittest

import _util as U
import cairn


class TestSlug(unittest.TestCase):
    def test_project_slug_spaces_and_apostrophes(self):
        self.assertEqual(
            cairn.project_slug("/Users/a/Documents/Fun Projects/claude cairn"),
            "-Users-a-Documents-Fun-Projects-claude-cairn")
        self.assertEqual(
            cairn.project_slug("/Users/a/Documents/Aman's Web Library"),
            "-Users-a-Documents-Aman-s-Web-Library")

    def test_project_slug_underscores(self):
        self.assertEqual(cairn.project_slug("/x/opus_4_6/python"),
                         "-x-opus-4-6-python")


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cairn-proj-")
        self._orig = cairn.projects_root
        cairn.projects_root = lambda: self.tmp

    def tearDown(self):
        cairn.projects_root = self._orig
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, slug, session, cwd):
        d = os.path.join(self.tmp, slug)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, session + ".jsonl")
        U.write_transcript(p, [U.user_text("hi", "2026-01-01T00:00:00Z"),
                               U.assistant_text("ok", "2026-01-01T00:00:01Z")])
        # stamp a real cwd into the first line
        with open(p, "w") as f:
            import json
            f.write(json.dumps({"type": "user", "cwd": cwd, "timestamp": "t",
                                "isMeta": False,
                                "message": {"role": "user", "content": "hi"}}) + "\n")
        return p

    def test_existing_path_returned(self):
        p = self._make("-proj", "sess-1", "/proj")
        self.assertEqual(cairn.resolve_transcript(p), p)

    def test_worktree_fallback_by_session_glob(self):
        real = self._make("-real-proj", "sess-abc", "/real/proj")
        # A worktree gives a bogus path under a different (nonexistent) dir.
        bogus = os.path.join(self.tmp, "-worktree", "sess-abc.jsonl")
        self.assertEqual(cairn.resolve_transcript(bogus), real)

    def test_resolve_by_cwd_only(self):
        real = self._make("-truncated-xyz", "sess-9", "/the/real/cwd")
        got = cairn.resolve_transcript(None, cwd="/the/real/cwd")
        self.assertEqual(got, real)

    def test_unresolvable_returns_none(self):
        self.assertIsNone(cairn.resolve_transcript("/nope/x.jsonl", session="missing"))


class TestDigest(unittest.TestCase):
    def _write(self, lines):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        return U.write_transcript(path, lines)

    def test_parses_all_line_types_without_crash(self):
        p = self._write([
            U.user_text("Build the thing", "2026-01-01T00:00:00Z"),
            U.assistant_text("I'll start by reading main.py", "2026-01-01T00:00:01Z"),
            U.assistant_tool("Read", {"file_path": "/proj/main.py"}, "2026-01-01T00:00:02Z"),
            U.user_tool_result("file contents here", "2026-01-01T00:00:03Z"),
            U.noise("2026-01-01T00:00:04Z"),
            U.compaction("2026-01-01T00:00:05Z"),
            U.assistant_text("Done", "2026-01-01T00:00:06Z"),
        ])
        d = cairn.build_digest(p, session="s", cwd="/proj")
        self.assertIn("Build the thing", d)
        self.assertIn("main.py", d)
        self.assertIn("--- COMPACTION", d)

    def test_ignores_thinking_text(self):
        p = self._write([
            U.assistant_thinking("SECRET_THOUGHT_SHOULD_NOT_APPEAR", "2026-01-01T00:00:00Z"),
            U.assistant_text("visible prose", "2026-01-01T00:00:01Z"),
        ])
        d = cairn.build_digest(p, session="s")
        self.assertNotIn("SECRET_THOUGHT", d)   # thinking is never read
        self.assertIn("visible prose", d)

    def test_filters_sidechain_and_meta(self):
        p = self._write([
            U.assistant_text("SIDECHAIN_TEXT", "2026-01-01T00:00:00Z", sidechain=True),
            U.user_text("META_CAVEAT", "2026-01-01T00:00:01Z", meta=True),
            U.user_text("real human ask", "2026-01-01T00:00:02Z"),
        ])
        d = cairn.build_digest(p, session="s")
        self.assertNotIn("SIDECHAIN_TEXT", d)
        self.assertNotIn("META_CAVEAT", d)
        self.assertIn("real human ask", d)

    def test_tool_result_list_content(self):
        p = self._write([
            U.assistant_tool("ToolSearch", {"query": "x"}, "2026-01-01T00:00:00Z"),
            U.user_tool_result([{"type": "text", "text": "LIST_RESULT_TEXT"},
                                {"type": "tool_reference", "tool_name": "Read"}],
                               "2026-01-01T00:00:01Z"),
        ])
        d = cairn.build_digest(p, session="s")   # must not crash on list content
        self.assertIn("LIST_RESULT_TEXT", d)

    def test_redaction_in_digest(self):
        p = self._write([
            U.assistant_text("my key is sk-ant-" + "abcd1234efgh5678ijkl here", "2026-01-01T00:00:00Z"),
        ])
        d = cairn.build_digest(p, session="s")
        self.assertIn("[REDACTED:anthropic_key]", d)
        self.assertNotIn("sk-ant-" + "abcd1234", d)

    def test_since_filter(self):
        p = self._write([
            U.assistant_text("OLD_TURN", "2026-01-01T00:00:00Z"),
            U.assistant_text("NEW_TURN", "2026-01-02T00:00:00Z"),
        ])
        d = cairn.build_digest(p, session="s", since="2026-01-01T12:00:00Z")
        self.assertNotIn("OLD_TURN", d)
        self.assertIn("NEW_TURN", d)

    def test_file_reference_index(self):
        p = self._write([
            U.assistant_tool("Read", {"file_path": "/a/one.py"}, "2026-01-01T00:00:00Z"),
            U.assistant_tool("Edit", {"file_path": "/a/two.py"}, "2026-01-01T00:00:01Z"),
            U.assistant_tool("Read", {"file_path": "/a/one.py"}, "2026-01-01T00:00:02Z"),
        ])
        d = cairn.build_digest(p, session="s")
        self.assertIn("## File & area references", d)
        self.assertIn("- /a/one.py", d)
        self.assertIn("- /a/two.py", d)
        self.assertEqual(d.count("- /a/one.py"), 1)   # deduped

    def test_budget_enforced_and_markers_kept(self):
        lines = [U.user_text("start", "2026-01-01T00:00:00Z")]
        big = "x" * 2000
        for i in range(400):
            ts = "2026-01-01T%02d:%02d:00Z" % (i // 60, i % 60)
            lines.append(U.assistant_text("turn %d %s" % (i, big), ts))
            if i % 100 == 50:
                lines.append(U.compaction(ts, pre=100000 + i, post=5000))
        p = self._write(lines)
        d = cairn.build_digest(p, session="s", budget=20000)
        # within budget (+ small slack for post-budget redaction; none here)
        self.assertLessEqual(len(d), 20000 + 200)
        self.assertEqual(d.count("--- COMPACTION"), 4)   # all 4 markers survive
        self.assertIn("omitted", d)


class TestRealTranscriptStreaming(unittest.TestCase):
    """Optional: prove streaming on the largest real transcript if present."""

    def test_large_real_transcript_is_fast(self):
        root = os.path.expanduser("~/.claude/projects")
        cands = sorted(glob.glob(os.path.join(root, "*", "*.jsonl")),
                       key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0,
                       reverse=True)
        cands = [c for c in cands if os.path.getsize(c) > 5_000_000]
        if not cands:
            self.skipTest("no large real transcript available")
        big = cands[0]
        t0 = time.time()
        d = cairn.build_digest(big, session="s", budget=48000)
        dt = time.time() - t0
        self.assertLessEqual(len(d), 48000 + 500)
        self.assertLess(dt, 10.0, "digest of %d MB took %.1fs" %
                        (os.path.getsize(big) // 1_000_000, dt))


if __name__ == "__main__":
    unittest.main()
