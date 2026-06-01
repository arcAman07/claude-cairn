"""Regression tests for the fixes from the independent review pass."""
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn


class TestRedactionBreadth(unittest.TestCase):
    def r(self, s):
        return cairn.redact_text(s)

    def test_aws_secret_assignment(self):  # H2
        out = self.r("aws_secret_access_key = wJalr" + "XUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        self.assertIn("[REDACTED:secret]", out)
        self.assertNotIn("wJalr" + "XUtnFEMI", out)

    def test_url_credential(self):  # H2
        out = self.r('DATABASE_URL="postgres://user:S3cretPass99@db.host/app"')
        self.assertIn("[REDACTED:url_password]", out)
        self.assertNotIn("S3cretPass99", out)

    def test_basic_auth_and_stripe_and_npm(self):  # H2
        self.assertIn("[REDACTED:basic_auth]", self.r("Authorization: Basic dXNlcjpwYXNzd29yZA=="))
        self.assertIn("[REDACTED:stripe_key]", self.r("sk_live_abcdefghijklmnop1234"))
        self.assertIn("[REDACTED:npm_token]", self.r("//registry/:_authToken=npm_" + "a" * 36))

    def test_quoted_no_space_secret_redacted(self):  # H2
        # an opaque (no-space) quoted secret value IS redacted
        self.assertIn("[REDACTED:secret]", self.r('password = "Sup3rS3cretToken99"'))

    def test_quoted_multiword_value_is_preserved_as_prose(self):  # audit MEDIUM #1
        # a multi-word quoted value is treated as PROSE (we never destroy prose);
        # documented best-effort trade-off (a spacey passphrase is the rare cost)
        out = self.r('password = "correct horse battery staple"')
        self.assertIn("correct horse battery staple", out)
        self.assertNotIn("[REDACTED", out)

    def test_separator_preserved_not_mangled(self):  # L1
        out = self.r("Set api_key = abcdefgh12345 then restart.")
        self.assertIn("api_key = [REDACTED:secret]", out)
        self.assertIn(" then restart.", out)

    def test_prose_still_safe(self):
        prose = "We reset the password flow and rotated the access key policy later."
        self.assertEqual(self.r(prose), prose)

    def test_redaction_before_truncation_in_digest(self):  # H3
        # A long line with a secret beyond the per-block truncation cap: the
        # secret must not survive as a fragment.
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        filler = "word " * 900  # ~4500 chars, past the 4000 claude cap
        U.write_transcript(p, [U.assistant_text(
            filler + " sk-ant-" + "SECRETKEY1234567890abcdefghij", "2026-01-01T00:00:00Z")])
        d = cairn.build_digest(p, session="s")
        self.assertNotIn("sk-ant-" + "SECRETKEY", d)
        os.remove(p)


class TestBudgetMarkerCap(unittest.TestCase):
    def test_many_markers_do_not_blow_budget(self):  # H1
        lines = [U.user_text("start", "2026-01-01T00:00:00Z")]
        big = "x" * 1000
        for i in range(2000):
            ts = "2026-01-%02dT%02d:00:00Z" % (1 + i // 100 % 27, i % 24)
            lines.append(U.assistant_text("t%d %s" % (i, big), ts))
            lines.append(U.compaction(ts))
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, lines)
        d = cairn.build_digest(p, session="s", budget=20000)
        self.assertLessEqual(len(d), 20000 + 500)        # not a 12x blowout
        self.assertIn("compaction markers omitted", d)    # capped & reported
        os.remove(p)


class TestStoreHardening(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-hard-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body="## Summary\nx\n", **kw):
        argv = ["--store", self.store, "save", "--name", name,
                "--session", kw.get("session", "ssss-1"), "--cwd", "/p"]
        return U.run_cli(argv, stdin_text=body)

    def test_duplicate_exact_name_rm_is_ambiguous(self):  # M1
        self.save("dup")
        self.save("dup")
        code, out = U.run_cli(["--store", self.store, "rm", "dup", "--yes"])
        self.assertEqual(code, 2)                          # refuses to guess
        self.assertIn("matches 2 notes", out)
        self.assertEqual(len(os.listdir(cairn.notes_dir(self.store))), 2)  # nothing deleted

    def test_rm_sidecar_does_not_overdelete_sibling(self):  # M2
        self.save("foo")
        self.save("foo-bar")
        foo = U.run_cli(["--store", self.store, "path", "foo"])[1].strip()
        foobar = U.run_cli(["--store", self.store, "path", "foo-bar"])[1].strip()
        sib_side = foobar[:-3] + ".pending-digest.txt"
        with open(sib_side, "w") as f:
            f.write("sibling staged digest")
        # delete foo by its exact id (foo is a substring of foo-bar -> ambiguous by name)
        foo_id = os.path.basename(foo)[:-3]
        U.run_cli(["--store", self.store, "rm", foo_id, "--yes"])
        self.assertTrue(os.path.exists(sib_side))          # sibling sidecar survives

    def test_update_refreshes_stale_summary(self):  # stale-summary bug
        self.save("note", body="## Summary\nOriginal state.\n")
        before = U.run_cli(["--store", self.store, "list", "--json"])[1]
        self.assertIn("Original state", before)
        U.run_cli(["--store", self.store, "save", "--name", "note", "--update"],
                  stdin_text="**Now:** Refactored to the new API; original plan dropped.")
        after = U.run_cli(["--store", self.store, "list", "--json"])[1]
        self.assertIn("Refactored to the new API", after)  # summary refreshed
        self.assertNotIn("Original state", after)

    def test_string_tags_coerced(self):  # M4
        self.save("t")
        note = U.run_cli(["--store", self.store, "path", "t"])[1].strip()
        text = open(note).read().replace('tags: []', 'tags: "single"')
        with open(note, "w") as f:
            f.write(text)
        meta, _ = cairn.parse_note(note)
        self.assertEqual(meta["tags"], ["single"])         # coerced to list
        code, out = U.run_cli(["--store", self.store, "list"])  # must not crash/garble
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
