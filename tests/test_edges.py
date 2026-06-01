"""Phase 6/7 hardening: edge cases that must degrade gracefully, never crash."""
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn


class TestTranscriptEdges(unittest.TestCase):
    def _w(self, lines):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        return U.write_transcript(p, lines)

    def test_empty_transcript(self):
        p = self._w([])
        d = cairn.build_digest(p, session="s", cwd="/p")   # must not crash
        self.assertIn("# Cairn digest", d)
        self.assertIn("(none)", d)                          # no file refs
        body, summary = cairn.build_extract(p, session="s", cwd="/p")
        self.assertIn("## Summary", body)

    def test_only_noise_and_malformed(self):
        p = self._w([U.noise("2026-01-01T00:00:00Z"), "{bad", "", "   "])
        d = cairn.build_digest(p, session="s")
        self.assertIn("# Cairn digest", d)                  # survives garbage

    def test_missing_transcript_digest_cli_errors_cleanly(self):
        code, out = U.run_cli(["digest", "/no/such/transcript.jsonl",
                               "--session", "nope-1111"])
        self.assertEqual(code, 1)                           # clean nonzero, no traceback


class TestNameEdges(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-name-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name):
        return U.run_cli(["--store", self.store, "save", "--name", name,
                          "--session", "ssss-1", "--cwd", "/p"],
                         stdin_text="## Summary\nbody\n")

    def test_name_with_spaces_roundtrips(self):
        code, _ = self.save("my big refactor")
        self.assertEqual(code, 0)
        # resolvable by exact name and substring; file is fs-safe
        code, out = U.run_cli(["--store", self.store, "path", "my big refactor"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(out.strip()))
        self.assertNotIn(" ", os.path.basename(out.strip()))   # slug removed spaces
        code, out = U.run_cli(["--store", self.store, "show", "big refactor"])
        self.assertEqual(code, 0)

    def test_unicode_only_name_has_distinct_slug(self):
        self.save("日本語")
        self.save("中文")
        files = os.listdir(cairn.notes_dir(self.store))
        self.assertEqual(len(files), 2)
        # neither degraded to a bare "note" collision
        self.assertTrue(all(f.startswith("note-") for f in files))
        self.assertNotEqual(files[0].split("--")[0], files[1].split("--")[0])

    def test_emoji_and_punctuation_name(self):
        code, _ = self.save("fix: the 🔥 bug (v2)!")
        self.assertEqual(code, 0)
        self.assertEqual(self.save("fix: the 🔥 bug (v2)!")[0], 0)  # again, no collide
        self.assertEqual(len(os.listdir(cairn.notes_dir(self.store))), 2)

    def test_large_note_body(self):
        big = "## Summary\n" + ("lorem ipsum " * 20000) + "\n"
        code, _ = U.run_cli(["--store", self.store, "save", "--name", "huge",
                             "--session", "s-1", "--cwd", "/p"], stdin_text=big)
        self.assertEqual(code, 0)
        meta, body = cairn.parse_note(
            os.path.join(cairn.notes_dir(self.store), self.save_idx()))
        self.assertGreater(len(body), 100000)

    def save_idx(self):
        import json
        return json.load(open(cairn.index_path(self.store)))["notes"][0]["file"]


class TestIndexEdges(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-idx-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def test_wrong_schema_version_rebuilds(self):
        U.run_cli(["--store", self.store, "save", "--name", "a", "--session",
                   "s-1", "--cwd", "/p"], stdin_text="## Summary\nx\n")
        import json
        p = cairn.index_path(self.store)
        d = json.load(open(p))
        d["schema_version"] = 999
        json.dump(d, open(p, "w"))
        idx = cairn.read_index(self.store)               # version mismatch -> rebuild
        self.assertEqual(idx["schema_version"], cairn.SCHEMA_VERSION)
        self.assertEqual(len(idx["notes"]), 1)

    def test_note_file_deleted_out_of_band_reindex(self):
        U.run_cli(["--store", self.store, "save", "--name", "a", "--session",
                   "s-1", "--cwd", "/p"], stdin_text="## Summary\nx\n")
        for f in os.listdir(cairn.notes_dir(self.store)):
            os.remove(os.path.join(cairn.notes_dir(self.store), f))
        idx = cairn.reindex(self.store)
        self.assertEqual(idx["notes"], [])


if __name__ == "__main__":
    unittest.main()
