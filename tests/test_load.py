"""Phase 3 gates: load is map-not-dump, merges, and is directory-independent."""
import os
import shutil
import tempfile
import unittest

import _util as U

# A note whose pointer list references a real file with sentinel content.
SECRET_FILE = None
NOTE_WITH_POINTER = """## Summary
Refactored the auth layer.

## Directions explored
- Rejected OAuth device flow: overkill for a CLI.

## Files & areas to look at
- {path} — the auth entry point

## Next step
Add refresh-token rotation.
"""


class TestLoad(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-load-")
        self.work = tempfile.mkdtemp(prefix="cairn-work-")
        # a real project file whose BODY must never appear in load output
        self.secret_file = os.path.join(self.work, "auth.py")
        with open(self.secret_file, "w") as f:
            f.write("SENTINEL_FILE_BODY = 'this must never be dumped by load'\n")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)
        shutil.rmtree(self.work, ignore_errors=True)

    def save(self, name, body, session="ssss-1"):
        return U.run_cli(["--store", self.store, "save", "--name", name,
                          "--session", session, "--cwd", "/proj"],
                         stdin_text=body)

    def test_load_is_map_not_dump(self):
        self.save("auth", NOTE_WITH_POINTER.format(path=self.secret_file))
        code, out = U.run_cli(["--store", self.store, "load", "auth"])
        self.assertEqual(code, 0)
        # distilled thinking IS present:
        self.assertIn("Refactored the auth layer", out)
        self.assertIn("Rejected OAuth device flow", out)
        self.assertIn("Add refresh-token rotation", out)
        # the POINTER (path) is present:
        self.assertIn(self.secret_file, out)
        # but the file's CONTENTS are NOT:
        self.assertNotIn("SENTINEL_FILE_BODY", out)
        # framing header that instructs map-not-dump:
        self.assertIn("Resumed Cairn context", out)
        self.assertIn("map, not a dump", out)

    def test_load_multiple_merge(self):
        self.save("one", "## Summary\nFIRST note.\n")
        self.save("two", "## Summary\nSECOND note.\n")
        code, out = U.run_cli(["--store", self.store, "load", "one", "two"])
        self.assertEqual(code, 0)
        self.assertIn("FIRST note", out)
        self.assertIn("SECOND note", out)
        self.assertIn("2 note(s)", out)
        self.assertEqual(out.count("=== Note:"), 2)

    def test_load_skips_missing_but_loads_present(self):
        self.save("real", "## Summary\nREAL note.\n")
        code, out = U.run_cli(["--store", self.store, "load", "real", "ghost"])
        self.assertEqual(code, 0)
        self.assertIn("REAL note", out)
        self.assertIn("skipped", out.lower())

    def test_load_all_missing_errors(self):
        code, out = U.run_cli(["--store", self.store, "load", "ghost"])
        self.assertEqual(code, 1)

    def test_load_works_from_different_directory(self):
        """Global store + cwd-independence: save 'here', chdir elsewhere, load."""
        self.save("portable", "## Summary\nPORTABLE_MARKER content.\n")
        old = os.getcwd()
        os.environ["CAIRN_HOME"] = self.store
        try:
            os.chdir(self.work)                      # a totally different directory
            code, out = U.run_cli(["load", "portable"])   # no --store; uses CAIRN_HOME
            self.assertEqual(code, 0)
            self.assertIn("PORTABLE_MARKER", out)
        finally:
            os.chdir(old)
            os.environ.pop("CAIRN_HOME", None)


if __name__ == "__main__":
    unittest.main()
