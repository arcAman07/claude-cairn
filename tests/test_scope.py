"""v1.5 — checkpoint scope modes (--scope full|focused|delta) + pin, and the
backward-compatibility guarantee that v1 notes (no scope/pinned) still parse."""
import json
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn


class ScopeCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-scope-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body="## Summary\nx\n", scope=None, pinned=False,
             tags="", session="aaaa1111-x", cwd="/proj"):
        argv = ["--store", self.store, "save", "--name", name,
                "--session", session, "--cwd", cwd]
        if scope:
            argv += ["--scope", scope]
        if pinned:
            argv += ["--pinned"]
        if tags:
            argv += ["--tags", tags]
        return U.run_cli(argv, stdin_text=body)

    def meta_of(self, name):
        note = cairn.resolve_notes(self.store, name)[0]
        m, _ = cairn.parse_note(os.path.join(cairn.notes_dir(self.store), note["file"]))
        return m

    # ---- scope roundtrip --------------------------------------------------
    def test_scope_full_roundtrips_to_frontmatter_and_index(self):
        self.save("toc", scope="full")
        self.assertEqual(self.meta_of("toc").get("scope"), "full")
        idx = cairn.read_index(self.store)
        self.assertEqual(idx["notes"][0].get("scope"), "full")

    def test_default_scope_is_focused(self):
        self.save("plain")                       # no --scope
        self.assertEqual(self.meta_of("plain").get("scope"), "focused")

    def test_scope_choices_rejected_when_invalid(self):
        # argparse rejects an out-of-set --scope by exiting (SystemExit), which is
        # the right behavior: an invalid flag must never silently save a note.
        with self.assertRaises(SystemExit):
            self.save("bad", scope="everything")

    # ---- pin --------------------------------------------------------------
    def test_pinned_roundtrips_and_sorts_first(self):
        self.save("old-unpinned")
        self.save("new-pinned", pinned=True)
        self.assertIs(self.meta_of("new-pinned").get("pinned"), True)
        code, out = U.run_cli(["--store", self.store, "list"])
        self.assertEqual(code, 0)
        # pinned sorts above the (newer) unpinned note despite recency
        self.assertLess(out.index("new-pinned"), out.index("old-unpinned"))
        self.assertIn("📌", out)

    def test_list_json_carries_scope_and_pinned(self):
        self.save("j", scope="full", pinned=True)
        code, out = U.run_cli(["--store", self.store, "list", "--json"])
        data = json.loads(out)[0]
        self.assertEqual(data["scope"], "full")
        self.assertIs(data["pinned"], True)

    def test_show_displays_scope(self):
        self.save("s", scope="delta")
        code, out = U.run_cli(["--store", self.store, "show", "s"])
        self.assertIn("scope: delta", out)

    # ---- update semantics -------------------------------------------------
    def test_update_without_scope_preserves_existing(self):
        self.save("u", scope="full")
        U.run_cli(["--store", self.store, "save", "--name", "u", "--update"],
                  stdin_text="**Now:** more.\n")
        self.assertEqual(self.meta_of("u").get("scope"), "full")

    def test_update_with_scope_overrides(self):
        self.save("u2", scope="full")
        U.run_cli(["--store", self.store, "save", "--name", "u2", "--update",
                   "--scope", "delta"], stdin_text="**Now:** more.\n")
        self.assertEqual(self.meta_of("u2").get("scope"), "delta")

    # ---- backward compatibility ------------------------------------------
    def test_v1_note_without_new_fields_still_parses(self):
        # Hand-write a v1-shaped note (no scope/pinned) and confirm readers cope.
        cairn.save_note(self.store, "legacy", "## Summary\nold note\n",
                        session="bbbb2222-y", cwd="/old")   # save_note default: no scope
        m = self.meta_of("legacy")
        self.assertIsNone(m.get("scope"))
        self.assertFalse(m.get("pinned"))
        # list + show must not crash and must render it without markers
        code, out = U.run_cli(["--store", self.store, "list"])
        self.assertEqual(code, 0)
        self.assertIn("legacy", out)
        self.assertNotIn("{None}", out)


if __name__ == "__main__":
    unittest.main()
