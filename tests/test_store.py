"""Phases 1-5 store behavior: save / index / reindex / path / extract / hook."""
import json
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn

SAMPLE = ("## Summary\nBuilt JWT auth; rejected session cookies.\n\n"
          "## Directions explored\n- Session cookies — rejected: needs sticky "
          "sessions across the fleet.\n- JWT — chosen.\n\n## Decisions\n"
          "- Use JWT with 15m expiry.\n\n## Open questions / assumptions\n"
          "- Refresh token storage TBD.\n\n## Files & areas to look at\n"
          "- /proj/auth.py\n- /proj/middleware.py\n\n## Next step\nWire refresh.\n")


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-store-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body=SAMPLE, extra=None):
        argv = ["--store", self.store, "save", "--name", name,
                "--session", "abcd1234-eeee", "--cwd", "/proj"]
        argv += extra or []
        return U.run_cli(argv, stdin_text=body)

    def index(self):
        with open(cairn.index_path(self.store)) as f:
            return json.load(f)


class TestSave(StoreCase):
    def test_save_writes_valid_note_and_index(self):
        code, out = self.save("auth refactor", extra=["--tags", "auth,jwt"])
        self.assertEqual(code, 0)
        idx = self.index()
        self.assertEqual(idx["schema_version"], cairn.SCHEMA_VERSION)
        self.assertEqual(len(idx["notes"]), 1)
        e = idx["notes"][0]
        for k in cairn.FM_KEYS:
            self.assertIn(k, e if k != "file" else {"file": 1})
        self.assertEqual(e["tags"], ["auth", "jwt"])
        self.assertEqual(e["source"], "manual")
        # frontmatter round-trips
        meta, body = cairn.parse_note(os.path.join(cairn.notes_dir(self.store), e["file"]))
        self.assertEqual(meta["name"], "auth refactor")
        self.assertEqual(meta["session_id"], "abcd1234-eeee")
        self.assertIn("rejected session cookies", meta["summary"])
        self.assertIn("## Directions explored", body)

    def test_filename_collision_proof(self):
        self.save("dup")
        self.save("dup")
        files = os.listdir(cairn.notes_dir(self.store))
        self.assertEqual(len(files), 2)        # distinct filenames
        self.assertEqual(len(self.index()["notes"]), 2)

    def test_summary_autoextracted_when_absent(self):
        self.save("x")
        self.assertTrue(self.index()["notes"][0]["summary"].startswith("Built JWT auth"))

    def test_explicit_summary_wins(self):
        self.save("y", extra=["--summary", "my own summary"])
        self.assertEqual(self.index()["notes"][0]["summary"], "my own summary")

    def test_unicode_name(self):
        code, _ = self.save("日本語ノート")
        self.assertEqual(code, 0)
        self.assertEqual(self.index()["notes"][0]["name"], "日本語ノート")


class TestReindexAndPath(StoreCase):
    def test_reindex_rebuilds_from_frontmatter(self):
        self.save("alpha")
        self.save("beta")
        os.remove(cairn.index_path(self.store))      # lose the index
        code, out = U.run_cli(["--store", self.store, "reindex"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.index()["notes"]), 2)

    def test_corrupt_index_autorebuilds(self):
        self.save("alpha")
        with open(cairn.index_path(self.store), "w") as f:
            f.write("{ broken json ]")
        idx = cairn.read_index(self.store)            # should silently rebuild
        self.assertEqual(len(idx["notes"]), 1)

    def test_path_prints_file(self):
        self.save("findme")
        code, out = U.run_cli(["--store", self.store, "path", "findme"])
        self.assertEqual(code, 0)
        self.assertTrue(out.strip().endswith(".md"))
        self.assertTrue(os.path.isfile(out.strip()))


class TestUpdate(StoreCase):
    def test_update_appends_without_duplication(self):
        self.save("note", extra=["--tags", "a"])
        before = self.index()["notes"][0]
        code, out = U.run_cli(
            ["--store", self.store, "save", "--name", "note", "--update",
             "--tags", "b", "--last-timestamp", "2026-02-02T00:00:00Z"],
            stdin_text="New finding: refresh tokens go in httpOnly cookies.")
        self.assertEqual(code, 0)
        notes = os.listdir(cairn.notes_dir(self.store))
        self.assertEqual(len(notes), 1)                 # still one file
        meta, body = cairn.parse_note(
            os.path.join(cairn.notes_dir(self.store), self.index()["notes"][0]["file"]))
        self.assertEqual(body.count("## Summary"), 1)   # original kept once
        self.assertIn("## Update —", body)              # appended section
        self.assertIn("httpOnly cookies", body)
        self.assertEqual(meta["tags"], ["a", "b"])      # merged
        self.assertEqual(meta["last_timestamp"], "2026-02-02T00:00:00Z")
        self.assertGreaterEqual(meta["updated"], before["created"])

    def test_update_missing_note_errors(self):
        code, out = U.run_cli(["--store", self.store, "save", "--name", "ghost",
                               "--update"], stdin_text="x")
        self.assertEqual(code, 1)


class TestExtractAndHookBody(StoreCase):
    def _transcript(self):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        return U.write_transcript(p, [
            U.user_text("Make the parser stream", "2026-01-01T00:00:00Z"),
            U.assistant_text("I'll avoid json.load and iterate lines instead.",
                             "2026-01-01T00:00:01Z"),
            U.assistant_tool("Edit", {"file_path": "/proj/parse.py"}, "2026-01-01T00:00:02Z"),
            U.assistant_text("Streaming works; next wire the budget.",
                             "2026-01-01T00:00:03Z"),
        ])

    def test_extract_produces_sectioned_body(self):
        body, summary = cairn.build_extract(self._transcript(), session="s", cwd="/proj")
        for sec in ("## Summary", "## Directions explored", "## Files & areas to look at",
                    "## Next step"):
            self.assertIn(sec, body)
        self.assertIn("Auto-captured at compaction", body)
        self.assertIn("/proj/parse.py", body)
        self.assertTrue(summary.startswith("Auto-captured"))


if __name__ == "__main__":
    unittest.main()
