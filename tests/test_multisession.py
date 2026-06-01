"""Multiple Claude sessions in ONE directory must resolve without error."""
import json
import os
import shutil
import tempfile
import unittest

import _util  # noqa: F401  (path setup)
import cairn


class MultiSessionCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cairn-proj-")
        self._orig = cairn.projects_root
        cairn.projects_root = lambda: self.root

    def tearDown(self):
        cairn.projects_root = self._orig
        shutil.rmtree(self.root, ignore_errors=True)

    def make(self, slug, session, cwd, mtime=None):
        d = os.path.join(self.root, slug)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, session + ".jsonl")
        with open(p, "w") as f:
            f.write(json.dumps({"type": "user", "cwd": cwd, "timestamp": "t",
                                "isMeta": False,
                                "message": {"role": "user", "content": "hi"}}) + "\n")
        if mtime:
            os.utime(p, (mtime, mtime))
        return p

    def test_three_sessions_same_dir_resolve_by_session(self):
        cwd = "/work/proj"
        # three sessions in the SAME project dir; A is OLDEST, C is NEWEST
        a = self.make("-work-proj", "aaaa1111-0000-0000-0000-000000000001", cwd, mtime=1000)
        b = self.make("-work-proj", "bbbb2222-0000-0000-0000-000000000002", cwd, mtime=2000)
        c = self.make("-work-proj", "cccc3333-0000-0000-0000-000000000003", cwd, mtime=3000)
        # by session id -> EXACTLY that one, regardless of mtime (no error, no wrong pick)
        self.assertEqual(cairn.resolve_transcript(session="aaaa1111-0000-0000-0000-000000000001", cwd=cwd), a)
        self.assertEqual(cairn.resolve_transcript(session="bbbb2222-0000-0000-0000-000000000002", cwd=cwd), b)
        self.assertEqual(cairn.resolve_transcript(session="cccc3333-0000-0000-0000-000000000003", cwd=cwd), c)

    def test_cwd_only_picks_newest_and_is_ambiguous(self):
        cwd = "/work/proj"
        self.make("-work-proj", "aaaa1111-x", cwd, mtime=1000)
        newest = self.make("-work-proj", "cccc3333-x", cwd, mtime=3000)
        # cwd-only resolves to newest (best-effort) -- never raises
        self.assertEqual(cairn.resolve_transcript(cwd=cwd), newest)

    def test_session_not_found_returns_none_not_other_session(self):
        cwd = "/work/proj"
        self.make("-work-proj", "aaaa1111-x", cwd)   # a different session exists
        # asking for a session that doesn't exist must NOT silently return the other
        self.assertIsNone(cairn.resolve_transcript(
            session="ffff9999-does-not-exist", cwd=cwd))

    def test_same_session_id_two_dirs_prefers_cwd(self):
        # pathological: same id in two project dirs (e.g. a moved/worktree session)
        sid = "dddd4444-0000-0000-0000-000000000004"
        other = self.make("-other", sid, "/other/cwd", mtime=3000)   # newer, wrong cwd
        mine = self.make("-work-proj", sid, "/work/proj", mtime=1000)  # older, right cwd
        self.assertEqual(cairn.resolve_transcript(session=sid, cwd="/work/proj"), mine)
        self.assertNotEqual(cairn.resolve_transcript(session=sid, cwd="/work/proj"), other)

    def test_transcripts_for_cwd_lists_all_newest_first(self):
        cwd = "/work/proj"
        self.make("-work-proj", "a1", cwd, mtime=1000)
        self.make("-work-proj", "b2", cwd, mtime=3000)
        self.make("-work-proj", "c3", cwd, mtime=2000)
        self.make("-other", "z9", "/somewhere/else", mtime=9999)   # different cwd
        got = cairn.transcripts_for_cwd(cwd)
        self.assertEqual([os.path.basename(p)[:2] for p in got], ["b2", "c3", "a1"])

    def test_resolve_list_cli(self):
        cwd = "/work/proj"
        self.make("-work-proj", "aaaa1111-x", cwd, mtime=1000)
        self.make("-work-proj", "bbbb2222-x", cwd, mtime=2000)
        code, out = _util.run_cli(["resolve", "--list", "--cwd", cwd])
        self.assertEqual(code, 0)
        self.assertIn("2 transcript(s)", out)
        self.assertIn("bbbb2222-x", out)


if __name__ == "__main__":
    unittest.main()
