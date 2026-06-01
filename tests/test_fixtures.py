"""Guard the QA fixtures: regenerate them and assert key digest properties."""
import os
import runpy
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lib"))
import cairn  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runpy.run_path(os.path.join(FX, "make_fixtures.py"), run_name="__main__")

    def d(self, name, cwd="/work"):
        return cairn.build_digest(os.path.join(FX, name), session="s", cwd=cwd)

    def test_all_nine_exist(self):
        for n in ["explore_heavy", "decision_heavy", "long_compacted", "trivial",
                  "secrets", "multi_topic", "code_reasoning", "worktree", "empty"]:
            self.assertTrue(os.path.isfile(os.path.join(FX, n + ".jsonl")), n)

    def test_exploration_has_rejections(self):
        d = self.d("explore_heavy.jsonl")
        self.assertIn("ruling fixed-window out", d)
        self.assertIn("rejecting it on memory cost", d)
        self.assertIn("Token bucket wins", d)

    def test_long_compacted_preserves_early_decision(self):
        d = self.d("long_compacted.jsonl")
        self.assertIn("event-sourcing", d)             # early decision survives
        self.assertIn("REJECTED: CRUD", d)
        self.assertIn("--- COMPACTION", d)             # boundary present

    def test_secrets_fully_redacted(self):
        d = self.d("secrets.jsonl", cwd="/work/deploy")
        for leak in ["sk-proj-" + "AbCd", "AKIA" + "IOSFODNN7EXAMPLE",
                     "ghp_" + "ABCDEFG", "wJalr" + "XUtnFEMI", "Sup3r" + "SecretPw99"]:
            self.assertNotIn(leak, d, "leaked %s" % leak)
        self.assertIn("[REDACTED", d)

    def test_empty_fixture_graceful(self):
        d = self.d("empty.jsonl")
        self.assertIn("# Cairn digest", d)


if __name__ == "__main__":
    unittest.main()
