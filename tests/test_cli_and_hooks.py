"""Cover the CLI entry-point wrappers and the hook modules IN-PROCESS so the
real code paths are measured (subprocess tests don't count toward coverage)."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

import _util as U
import cairn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import precompact_capture          # noqa: E402
import session_start_autoload      # noqa: E402


def _transcript():
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    return U.write_transcript(p, [
        U.user_text("Add a healthcheck endpoint", "2026-01-01T00:00:00Z"),
        U.assistant_text("I'll add GET /healthz returning 200.", "2026-01-01T00:00:01Z"),
        U.assistant_tool("Edit", {"file_path": "/srv/app.py"}, "2026-01-01T00:00:02Z"),
        U.assistant_text("Done; wired the route.", "2026-01-01T00:00:03Z"),
    ])


class TestCLIWrappers(unittest.TestCase):
    def setUp(self):
        self.t = _transcript()
        self.store = tempfile.mkdtemp(prefix="cairn-cli-")

    def tearDown(self):
        os.remove(self.t)
        shutil.rmtree(self.store, ignore_errors=True)

    def test_resolve_digest_extract_redact_reindex_path(self):
        code, out = U.run_cli(["resolve", self.t])
        self.assertEqual((code, out.strip()), (0, self.t))

        code, out = U.run_cli(["digest", self.t, "--session", "s", "--cwd", "/srv"])
        self.assertEqual(code, 0)
        self.assertIn("healthz", out)

        code, out = U.run_cli(["extract", self.t, "--session", "s", "--cwd", "/srv"])
        self.assertEqual(code, 0)
        self.assertIn("## Summary", out)

        code, out = U.run_cli(["redact"], stdin_text="key sk-ant-" + "abcd1234efgh5678ijkl")
        self.assertIn("[REDACTED:anthropic_key]", out)

        # save one, then path + reindex
        U.run_cli(["--store", self.store, "save", "--name", "n", "--session", "s",
                   "--cwd", "/srv"], stdin_text="## Summary\nx\n")
        code, out = U.run_cli(["--store", self.store, "path", "n"])
        self.assertTrue(out.strip().endswith(".md"))
        code, out = U.run_cli(["--store", self.store, "reindex"])
        self.assertIn("Reindexed 1", out)

    def test_digest_missing_transcript_returns_1(self):
        code, _ = U.run_cli(["digest", "/no/such.jsonl", "--session", "z"])
        self.assertEqual(code, 1)

    def test_export_and_show_and_load_cli(self):
        U.run_cli(["--store", self.store, "save", "--name", "exp", "--session", "s",
                   "--cwd", "/srv"], stdin_text="## Summary\nbody here\n")
        self.assertEqual(U.run_cli(["--store", self.store, "export", "exp"])[0], 0)
        self.assertEqual(U.run_cli(["--store", self.store, "show", "exp"])[0], 0)
        self.assertEqual(U.run_cli(["--store", self.store, "load", "exp"])[0], 0)

    def test_selftest_passes(self):
        code, out = U.run_cli(["selftest"])
        self.assertEqual(code, 0)
        self.assertIn("OK", out)


def _run_hook(module, stdin_text, store):
    old_in, old_out, old_env = sys.stdin, sys.stdout, os.environ.get("CAIRN_HOME")
    os.environ["CAIRN_HOME"] = store
    sys.stdin = io.StringIO(stdin_text)
    sys.stdout = io.StringIO()
    try:
        rc = module.main()
        return rc, sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_in, old_out
        if old_env is None:
            os.environ.pop("CAIRN_HOME", None)
        else:
            os.environ["CAIRN_HOME"] = old_env


class TestHooksInProcess(unittest.TestCase):
    def setUp(self):
        self.t = _transcript()
        self.store = tempfile.mkdtemp(prefix="cairn-hookip-")

    def tearDown(self):
        os.remove(self.t)
        shutil.rmtree(self.store, ignore_errors=True)

    def _stdin(self, **over):
        d = {"session_id": "hookip01-aaaa", "transcript_path": self.t,
             "cwd": "/srv/myrepo", "trigger": "auto"}
        d.update(over)
        return json.dumps(d)

    def test_precompact_captures_and_rolls(self):
        rc, out = _run_hook(precompact_capture, self._stdin(), self.store)
        self.assertEqual(rc, 0)
        idx = cairn.read_index(self.store)
        self.assertEqual(len(idx["notes"]), 1)
        self.assertEqual(idx["notes"][0]["source"], "auto")
        # second compaction in the same session REFRESHES (rolling), not a 2nd note
        rc, out = _run_hook(precompact_capture, self._stdin(), self.store)
        self.assertEqual(rc, 0)
        self.assertEqual(len(cairn.read_index(self.store)["notes"]), 1)

    def test_precompact_bad_and_empty_input_exit_zero(self):
        self.assertEqual(_run_hook(precompact_capture, "", self.store)[0], 0)
        self.assertEqual(_run_hook(precompact_capture, "{bad", self.store)[0], 0)
        self.assertEqual(_run_hook(precompact_capture, "[]", self.store)[0], 0)
        self.assertEqual(len(cairn.read_index(self.store)["notes"]), 0)

    def test_session_start_autoload_suggests_when_note_exists(self):
        # no note for this cwd -> no output
        rc, out = _run_hook(session_start_autoload,
                            json.dumps({"cwd": "/srv/myrepo", "source": "startup"}),
                            self.store)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")
        # add a note for that cwd, then it should suggest loading it
        U.run_cli(["--store", self.store, "save", "--name", "prev", "--session",
                   "s", "--cwd", "/srv/myrepo"], stdin_text="## Summary\nprior work\n")
        rc, out = _run_hook(session_start_autoload,
                            json.dumps({"cwd": "/srv/myrepo"}), self.store)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("prev", ctx)
        self.assertIn("/cairn:load", ctx)

    def test_session_start_bad_input_exit_zero(self):
        self.assertEqual(_run_hook(session_start_autoload, "{bad", self.store)[0], 0)


if __name__ == "__main__":
    unittest.main()
