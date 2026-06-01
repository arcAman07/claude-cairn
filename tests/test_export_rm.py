"""Phase 4 gates: export (cold-readable) and rm (safe, idempotent)."""
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn

BODY = ("## Summary\nShipped the cache layer.\n\n## Decisions\n"
        "- LRU with 1k entries.\n\n## Next step\nAdd metrics.\n")


class Phase4Case(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-p4-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body=BODY, source="manual"):
        return U.run_cli(["--store", self.store, "save", "--name", name,
                          "--session", "ssss-1", "--cwd", "/p",
                          "--source", source], stdin_text=body)


class TestExport(Phase4Case):
    def test_export_default_path_and_clean(self):
        self.save("cache-layer")
        code, out = U.run_cli(["--store", self.store, "export", "cache-layer"])
        self.assertEqual(code, 0)
        dest = out.split("Exported to", 1)[1].strip()
        self.assertTrue(os.path.isfile(dest))
        text = open(dest).read()
        # cold-readable: has a title + body, no internal frontmatter keys
        self.assertIn("# cache-layer", text)
        self.assertIn("Shipped the cache layer", text)
        self.assertNotIn("session_id:", text)
        self.assertNotIn("\nid:", text)
        self.assertNotIn("---\nname:", text)

    def test_export_custom_out(self):
        self.save("note")
        dest = os.path.join(self.store, "myexport.md")
        code, out = U.run_cli(["--store", self.store, "export", "note", "--out", dest])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(dest))

    def test_export_strips_auto_banner(self):
        self.save("auto-note", body="> **Auto-captured at compaction — raw.**\n\n"
                  "## Summary\nStuff happened.\n", source="auto")
        code, out = U.run_cli(["--store", self.store, "export", "auto-note"])
        dest = out.split("Exported to", 1)[1].strip()
        self.assertNotIn("Auto-captured at compaction", open(dest).read())


class TestRm(Phase4Case):
    def _files(self):
        return os.listdir(cairn.notes_dir(self.store))

    def test_rm_dry_run_then_confirm(self):
        self.save("doomed")
        code, out = U.run_cli(["--store", self.store, "rm", "doomed"])
        self.assertEqual(code, 0)
        self.assertIn("Would delete", out)
        self.assertEqual(len(self._files()), 1)          # not yet deleted
        code, out = U.run_cli(["--store", self.store, "rm", "doomed", "--yes"])
        self.assertEqual(code, 0)
        self.assertIn("Deleted", out)
        self.assertEqual(len(self._files()), 0)          # file gone
        import json
        idx = json.load(open(cairn.index_path(self.store)))
        self.assertEqual(idx["notes"], [])               # index entry gone

    def test_rm_missing_is_safe(self):
        code, out = U.run_cli(["--store", self.store, "rm", "ghost", "--yes"])
        self.assertEqual(code, 0)
        self.assertIn("No note matches", out)

    def test_rm_also_removes_pending_digest_sidecar(self):
        self.save("withside")
        note = U.run_cli(["--store", self.store, "path", "withside"])[1].strip()
        side = note[:-3] + ".pending-digest.txt"
        with open(side, "w") as f:
            f.write("staged digest")
        U.run_cli(["--store", self.store, "rm", "withside", "--yes"])
        self.assertFalse(os.path.exists(side))


class TestSinceBranching(unittest.TestCase):
    """digest --since is timestamp-based, so it is robust to branched chains."""

    def test_since_survives_forked_parent(self):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        U.write_transcript(p, [
            U.assistant_text("OLD before checkpoint", "2026-01-01T00:00:00Z"),
            # a compaction sets parentUuid=null (a fork in the chain)
            U.compaction("2026-01-01T06:00:00Z"),
            # a retry sibling (same logical position) -- still time-ordered
            U.assistant_text("NEW after checkpoint A", "2026-01-02T00:00:00Z"),
            U.assistant_text("NEW after checkpoint B", "2026-01-02T01:00:00Z"),
        ])
        d = cairn.build_digest(p, session="s", since="2026-01-01T12:00:00Z")
        self.assertNotIn("OLD before checkpoint", d)
        self.assertIn("NEW after checkpoint A", d)
        self.assertIn("NEW after checkpoint B", d)
        os.remove(p)


if __name__ == "__main__":
    unittest.main()
