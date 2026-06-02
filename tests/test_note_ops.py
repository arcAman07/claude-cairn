"""v1.5 — rename / tag / pin / unpin / recent."""
import json
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn


class OpsCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-ops-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body="## Summary\nx\n", tags="", session="aaaa1111-x", cwd="/proj"):
        argv = ["--store", self.store, "save", "--name", name,
                "--session", session, "--cwd", cwd]
        if tags:
            argv += ["--tags", tags]
        return U.run_cli(argv, stdin_text=body)

    def cli(self, *argv):
        return U.run_cli(["--store", self.store, *argv])

    def meta_of(self, name):
        note = cairn.resolve_notes(self.store, name)[0]
        m, _ = cairn.parse_note(os.path.join(cairn.notes_dir(self.store), note["file"]))
        return m

    # ---- rename -----------------------------------------------------------
    def test_rename_changes_name_keeps_id(self):
        self.save("oldname", tags="x")
        old_id = self.meta_of("oldname")["id"]
        code, out = self.cli("rename", "oldname", "newname")
        self.assertEqual(code, 0)
        self.assertIn("Renamed", out)
        m = self.meta_of("newname")
        self.assertEqual(m["name"], "newname")
        self.assertEqual(m["id"], old_id)                       # id is immutable
        # index reflects the new name
        idx = {n["id"]: n for n in cairn.read_index(self.store)["notes"]}
        self.assertEqual(idx[old_id]["name"], "newname")

    def test_rename_missing_is_graceful(self):
        code, out = self.cli("rename", "ghost", "x")
        self.assertEqual(code, 0)
        self.assertIn("No note matches", out)

    def test_rename_ambiguous_requires_id(self):
        self.save("dup")
        self.save("dup")
        code, out = self.cli("rename", "dup", "x")
        self.assertEqual(code, 2)
        self.assertIn("pass --id", out)
        # disambiguating with --id succeeds
        target = cairn.read_index(self.store)["notes"][0]
        code2, _ = self.cli("rename", "dup", "x", "--id", target["id"])
        self.assertEqual(code2, 0)

    # ---- tag --------------------------------------------------------------
    def test_tag_add_and_remove(self):
        self.save("t", tags="a,b")
        self.cli("tag", "t", "--add", "c,d", "--remove", "a")
        self.assertEqual(sorted(self.meta_of("t")["tags"]), ["b", "c", "d"])

    def test_tag_add_is_idempotent(self):
        self.save("t2", tags="a")
        self.cli("tag", "t2", "--add", "a")
        self.assertEqual(self.meta_of("t2")["tags"], ["a"])      # no dup

    # ---- pin / unpin ------------------------------------------------------
    def test_pin_then_unpin(self):
        self.save("p")
        self.cli("pin", "p")
        self.assertIs(self.meta_of("p").get("pinned"), True)
        self.cli("unpin", "p")
        # unpin removes the field entirely -> clean v1 frontmatter
        self.assertNotIn("pinned", self.meta_of("p"))

    def test_pinned_sorts_first_in_recent(self):
        self.save("first")
        self.save("second")
        self.cli("pin", "first")                                 # older, but pinned
        code, out = self.cli("recent")
        self.assertEqual(code, 0)
        self.assertLess(out.index("first"), out.index("second"))

    # ---- recent -----------------------------------------------------------
    def test_recent_respects_n(self):
        for i in range(5):
            self.save("note%d" % i)
        code, out = self.cli("recent", "--n", "2")
        self.assertEqual(code, 0)
        self.assertIn("2 most-recent", out)

    def test_recent_json(self):
        self.save("j")
        code, out = self.cli("recent", "--json")
        self.assertEqual(len(json.loads(out)), 1)


if __name__ == "__main__":
    unittest.main()
