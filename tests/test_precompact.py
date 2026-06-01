"""Phase 5 gates: PreCompact hook captures, stages, and never crashes."""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _util as U

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "precompact_capture.py")


def run_hook(stdin_text, store, env_extra=None):
    env = dict(os.environ)
    env["CAIRN_HOME"] = store
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, HOOK], input=stdin_text, text=True,
                       capture_output=True, env=env, timeout=30)
    return p


class TestPreCompact(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-hook-")
        fd, self.transcript = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(self.transcript, [
            U.user_text("Build the auto-capture hook", "2026-01-01T00:00:00Z"),
            U.assistant_text("I'll preserve the trace mechanically before compaction.",
                             "2026-01-01T00:00:01Z"),
            U.assistant_tool("Edit", {"file_path": "/proj/hook.py"}, "2026-01-01T00:00:02Z"),
            U.assistant_text("Staged a digest for later distillation.",
                             "2026-01-01T00:00:03Z"),
        ])

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)
        os.remove(self.transcript)

    def _stdin(self, **over):
        d = {"session_id": "hook1234-aaaa", "transcript_path": self.transcript,
             "cwd": "/proj/myrepo", "hook_event_name": "PreCompact",
             "trigger": "auto"}
        d.update(over)
        return json.dumps(d)

    def _notes(self):
        return glob.glob(os.path.join(self.store, "notes", "*.md"))

    def test_captures_auto_note_with_banner_and_sidecar(self):
        p = run_hook(self._stdin(), self.store)
        self.assertEqual(p.returncode, 0, p.stderr)
        notes = self._notes()
        self.assertEqual(len(notes), 1)
        text = open(notes[0]).read()
        self.assertIn('source: "auto"', text)
        self.assertIn("Auto-captured at compaction", text)        # banner
        self.assertIn("/proj/hook.py", text)                      # file pointer
        self.assertIn("auto", text)                               # tag
        # staged digest sidecar exists
        side = notes[0][:-3] + ".pending-digest.txt"
        self.assertTrue(os.path.isfile(side))
        self.assertIn("Cairn digest", open(side).read())
        # registered in the index
        idx = json.load(open(os.path.join(self.store, "index.json")))
        self.assertEqual(idx["notes"][0]["source"], "auto")

    def test_empty_stdin_exits_zero_no_crash(self):
        p = run_hook("", self.store)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(self._notes()), 0)

    def test_malformed_json_exits_zero(self):
        p = run_hook("{ not json at all", self.store)
        self.assertEqual(p.returncode, 0)

    def test_missing_transcript_exits_zero(self):
        p = run_hook(self._stdin(transcript_path="/no/such/file.jsonl",
                                 session_id="missing9-zzzz"), self.store)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(self._notes()), 0)

    def test_concurrent_invocations_no_index_corruption(self):
        env = dict(os.environ)
        env["CAIRN_HOME"] = self.store
        procs = [subprocess.Popen([sys.executable, HOOK], stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  text=True, env=env) for _ in range(5)]
        for i, pr in enumerate(procs):
            pr.stdin.write(self._stdin(session_id="conc%04d-aaaa" % i))
            pr.stdin.close()
        for pr in procs:
            self.assertEqual(pr.wait(timeout=30), 0)
        # all 5 note files written (filenames are collision-proof)
        self.assertEqual(len(self._notes()), 5)
        # index.json is still valid JSON; reindex recovers full count regardless
        import cairn
        cairn.read_index(self.store)                    # must not raise / corrupt
        self.assertEqual(len(cairn.reindex(self.store)["notes"]), 5)
        json.load(open(os.path.join(self.store, "index.json")))  # parseable


if __name__ == "__main__":
    unittest.main()
