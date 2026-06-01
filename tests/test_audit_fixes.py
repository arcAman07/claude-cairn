"""Regression tests for findings from the independent audits."""
import json
import os
import shutil
import tempfile
import time
import unittest

import _util as U
import cairn


class TestRedactionAudit(unittest.TestCase):
    def test_url_cred_redos_bounded(self):  # #1 HIGH
        s = "com.example.service.module.handler." * 3600  # ~123KB dotted, no "://"
        t0 = time.time()
        cairn.redact_text(s)
        self.assertLess(time.time() - t0, 1.0)            # was ~9.5s (quadratic)

    def test_pem_redos_bounded(self):  # #3 LOW
        s = "-----BEGIN RSA PRIVATE KEY-----\n" * 3000
        t0 = time.time()
        cairn.redact_text(s)
        self.assertLess(time.time() - t0, 1.0)

    def test_json_quoted_key_secrets(self):  # #2 MEDIUM
        for s, secret in [
            ('{"password": "Sup3rS3cr3tDBpass"}', "Sup3rS3cr3tDBpass"),
            ('"api_key":"live_abcdef123456"', "live_abcdef123456"),
            ("'password':'mySecretPass1'", "mySecretPass1"),
            ('{"db":{"password":"nestedSecret9"}}', "nestedSecret9"),
        ]:
            out = cairn.redact_text(s)
            self.assertNotIn(secret, out, s)
            self.assertIn("[REDACTED:secret]", out)

    def test_json_nonsecret_keys_untouched(self):
        s = '{"name": "John Doe", "username": "admin"}'
        self.assertEqual(cairn.redact_text(s), s)

    def test_plain_assignments_still_redact(self):
        self.assertIn("[REDACTED:secret]", cairn.redact_text("password = hunter2hunter2"))
        self.assertIn("[REDACTED:url_password]",
                      cairn.redact_text("postgres://u:S3cretPass99@h/d"))


class TestRound3Audit(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-r3-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body="## Summary\nx\n"):
        return U.run_cli(["--store", self.store, "save", "--name", name,
                          "--session", "s-1", "--cwd", "/p"], stdin_text=body)

    def test_over_redaction_preserves_prose(self):  # #1 MEDIUM, #2 LOW
        for s in ['He said the secret: "the cake is a lie and you know it"',
                  'Note about token: "we should rotate these every 90 days"',
                  "Secret: hidden inside the cavern walls",
                  "Tokenizer: handles unicode normalization",
                  "secretary: schedules all the meetings today"]:
            self.assertEqual(cairn.redact_text(s), s, "over-redacted: %r" % s)

    def test_real_secrets_still_redacted(self):
        for s in ['password = hunter2hunter2', '{"api_key":"Sup3rS3cretAB12"}',
                  "AUTH_TOKEN=abcdef1234567890"]:
            self.assertIn("[REDACTED", cairn.redact_text(s))

    def test_numeric_date_does_not_crash_list_find(self):  # #5 HIGH
        self.save("n")
        p = os.path.join(cairn.notes_dir(self.store),
                         os.listdir(cairn.notes_dir(self.store))[0])
        txt = open(p).read().replace('created: "', 'created: ', 1)  # make it numeric-ish
        # force a genuinely numeric value
        import re as _re
        txt = _re.sub(r'created: [^\n]+', 'created: 20260601', txt)
        with open(p, "w") as f:
            f.write(txt)
        cairn.reindex(self.store)
        self.assertEqual(U.run_cli(["--store", self.store, "list"])[0], 0)
        self.assertEqual(U.run_cli(["--store", self.store, "find", "x"])[0], 0)

    def test_export_bare_out_filename(self):  # #7 MEDIUM
        self.save("exp")
        d = os.getcwd()
        try:
            os.chdir(self.store)
            code, out = U.run_cli(["--store", self.store, "export", "exp", "--out", "bare.md"])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(self.store, "bare.md")))
        finally:
            os.chdir(d)

    def test_stale_index_file_does_not_crash(self):  # #8 MEDIUM
        self.save("ghost")
        for f in os.listdir(cairn.notes_dir(self.store)):
            if f.endswith(".md"):
                os.remove(os.path.join(cairn.notes_dir(self.store), f))  # delete file, keep index
        for cmd in (["show", "ghost"], ["load", "ghost"], ["export", "ghost"],
                    ["path", "ghost"]):
            code, out = U.run_cli(["--store", self.store] + cmd)
            self.assertIn(code, (0, 1, 2))                 # handled, not a traceback
        # update path too
        code, _ = U.run_cli(["--store", self.store, "save", "--name", "ghost",
                             "--update"], stdin_text="x")
        self.assertEqual(code, 1)

    def test_negative_budget_clamped(self):  # #3 LOW
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, [U.assistant_text("hello world", "2026-01-01T00:00:00Z")])
        d = cairn.build_digest(p, session="s", budget=-100)
        self.assertEqual(len(d), 0)                        # not a negative slice
        os.remove(p)

    def test_string_tags_in_index_not_char_iterated(self):  # #11 LOW
        self.save("t")
        idxp = cairn.index_path(self.store)
        d = json.load(open(idxp))
        d["notes"][0]["tags"] = "single"                   # hand-edited bad index
        json.dump(d, open(idxp, "w"))
        code, out = U.run_cli(["--store", self.store, "list"])
        self.assertEqual(code, 0)
        self.assertIn("#single", out)                      # not "#s #i #n #g #l #e"

    def test_find_missing_file_key_no_crash(self):  # #12 LOW
        self.save("a")
        idxp = cairn.index_path(self.store)
        d = json.load(open(idxp))
        d["notes"][0].pop("file", None)                    # malformed entry
        json.dump(d, open(idxp, "w"))
        self.assertEqual(U.run_cli(["--store", self.store, "find", "x"])[0], 0)


class TestResolveSaveAudit(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-af-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body="## Summary\nx\n"):
        return U.run_cli(["--store", self.store, "save", "--name", name,
                          "--session", "s-1", "--cwd", "/p"], stdin_text=body)

    def test_empty_query_matches_nothing(self):  # #16 HIGH
        self.save("only-note")
        self.assertEqual(cairn.resolve_notes(self.store, ""), [])
        self.assertEqual(cairn.resolve_notes(self.store, "   "), [])
        code, out = U.run_cli(["--store", self.store, "rm", "", "--yes"])
        self.assertEqual(len(os.listdir(cairn.notes_dir(self.store))), 1)  # not deleted

    def test_update_id_no_match_errors(self):  # #17 MEDIUM
        self.save("n1")
        self.save("n1")  # duplicate name
        code, _ = U.run_cli(["--store", self.store, "save", "--name", "n1",
                             "--update", "--id", "does-not-exist"], stdin_text="x")
        self.assertEqual(code, 1)  # errors instead of updating the wrong note

    def test_nonstring_tag_elements_coerced(self):  # #18 LOW
        self.save("t")
        p = os.path.join(cairn.notes_dir(self.store), os.listdir(cairn.notes_dir(self.store))[0])
        txt = open(p).read().replace("tags: []", "tags: [123, true]")
        with open(p, "w") as f:
            f.write(txt)
        meta, _ = cairn.parse_note(p)
        self.assertEqual(meta["tags"], ["123", "True"])      # coerced to str
        self.assertEqual(U.run_cli(["--store", self.store, "list"])[0], 0)  # no crash

    def test_digest_session_header_robust_ext(self):  # #10 NIT
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, [U.assistant_text("hi", "2026-01-01T00:00:00Z")])
        # resolve uses basename without extension assumptions
        renamed = p[:-len(".jsonl")] + ".txt"
        os.rename(p, renamed)
        code, out = U.run_cli(["digest", renamed])
        self.assertEqual(code, 0)
        self.assertIn("# session: ", out)
        self.assertNotIn(".tx", out.split("# session:")[1].split("\n")[0])  # no mangled ext
        os.remove(renamed)


class TestBudgetCeiling(unittest.TestCase):
    def test_tiny_budget_hard_capped(self):  # #5 MEDIUM
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, [U.assistant_tool("Read", {"file_path": "/a/%d.py" % i},
                                                "2026-01-01T00:00:%02dZ" % i)
                               for i in range(40)])
        d = cairn.build_digest(p, session="s", budget=3000)
        self.assertLessEqual(len(d), 3000)                  # hard ceiling honoured
        os.remove(p)

    def test_tiny_budget_keeps_pointer_block(self):  # re-audit LOW
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, [U.assistant_tool("Read", {"file_path": "/imp/f%d.py" % i},
                                                "2026-01-01T00:00:%02dZ" % i)
                               for i in range(30)])
        for b in (1500, 3000, 6500, 48000):                 # pointers survive at every budget
            d = cairn.build_digest(p, session="s", budget=b)
            self.assertLessEqual(len(d), b)
            self.assertIn("## File & area references", d, "budget %d dropped pointers" % b)
            self.assertIn("/imp/f", d)
        os.remove(p)


class TestFileLockAudit(unittest.TestCase):
    def test_exit_does_not_delete_successors_lock(self):  # #6 MEDIUM
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "x.lock")
            lock = cairn.FileLock(p)
            lock.__enter__()
            self.assertTrue(lock.acquired)
            # simulate a successor stale-stealing: replace the file (new inode)
            os.unlink(p)
            with open(p, "w") as f:
                f.write("successor")
            lock.__exit__()
            self.assertTrue(os.path.exists(p))              # successor's lock survives
            self.assertEqual(open(p).read(), "successor")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestRollAutoNote(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-roll-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def files(self):
        return os.listdir(cairn.notes_dir(self.store))

    def roll(self, session, summary="s"):
        return cairn.roll_auto_note(self.store, session, "auto-proj",
                                    "## Summary\n%s\n" % summary, summary, "/p")

    def test_rolling_one_per_session(self):  # #12, #13
        self.roll("sess-A", "first")
        self.roll("sess-A", "second")
        self.roll("sess-A", "third")
        self.assertEqual(len(self.files()), 1)
        idx = cairn.read_index(self.store)
        self.assertEqual(len(idx["notes"]), 1)
        self.assertEqual(idx["notes"][0]["summary"], "third")   # refreshed in place

    def test_separate_sessions_separate_notes(self):
        self.roll("sess-A")
        self.roll("sess-B")
        self.assertEqual(len(self.files()), 2)

    def test_corrupt_existing_falls_through(self):  # #14
        p = self.roll("sess-A")
        with open(p, "w") as f:
            f.write("not a valid note, no frontmatter")
        self.roll("sess-A", "recovered")                # must not raise
        idx = cairn.read_index(self.store)
        # a fresh valid note now represents the session
        autos = [n for n in idx["notes"] if n.get("session_id") == "sess-A"]
        self.assertTrue(any(n["summary"] == "recovered" for n in autos))

    def test_stale_index_entry_deleted_file(self):  # #11
        p = self.roll("sess-A")
        os.remove(p)                                    # delete file, leave index entry
        self.roll("sess-A", "afterdelete")              # must not raise; recreates
        self.assertGreaterEqual(len(self.files()), 1)
        idx = cairn.read_index(self.store)
        self.assertTrue(any(n["summary"] == "afterdelete" for n in idx["notes"]))


if __name__ == "__main__":
    unittest.main()
