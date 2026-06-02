"""v1.5 — merge (deterministic structural merge) + diff (structural compare)."""
import json
import os
import shutil
import tempfile
import unittest

import _util as U
import cairn

NOTE_A = ("## Summary\nJWT auth.\n\n## Decisions\n- Chose JWT.\n\n"
          "## Files & areas to look at\n- src/auth.py — tokens\n- src/mw.py — middleware\n\n"
          "## Next step\nAdd refresh.\n")
NOTE_B = ("## Summary\nRate limiting.\n\n## Open questions / assumptions\n- Redis?\n\n"
          "## Files & areas to look at\n- src/limit.py — bucket\n- src/mw.py — middleware\n\n"
          "## Next step\nPick a store.\n")


class MergeDiffCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-md-")
        U.run_cli(["--store", self.store, "save", "--name", "alpha",
                   "--tags", "auth", "--cwd", "/p"], stdin_text=NOTE_A)
        U.run_cli(["--store", self.store, "save", "--name", "beta",
                   "--tags", "perf", "--cwd", "/p"], stdin_text=NOTE_B)

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def cli(self, *argv):
        return U.run_cli(["--store", self.store, *argv])

    def body_of(self, name):
        note = cairn.resolve_notes(self.store, name)[0]
        _, b = cairn.parse_note(os.path.join(cairn.notes_dir(self.store), note["file"]))
        return b

    def meta_of(self, name):
        note = cairn.resolve_notes(self.store, name)[0]
        m, _ = cairn.parse_note(os.path.join(cairn.notes_dir(self.store), note["file"]))
        return m

    # ---- merge ------------------------------------------------------------
    def test_merge_aggregates_and_dedupes(self):
        code, out = self.cli("merge", "--name", "combined", "alpha", "beta")
        self.assertEqual(code, 0)
        body = self.body_of("combined")
        # both source summaries are present
        self.assertIn("JWT auth.", body)
        self.assertIn("Rate limiting.", body)
        # shared pointer appears exactly once in the unioned Files section
        files = cairn._section_lines(body, "Files & areas to look at")
        mw = [ln for ln in files if "src/mw.py" in ln]
        self.assertEqual(len(mw), 1)
        # unique pointers from each source are present
        self.assertTrue(any("src/auth.py" in ln for ln in files))
        self.assertTrue(any("src/limit.py" in ln for ln in files))

    def test_merge_sets_parent_scope_and_union_tags(self):
        self.cli("merge", "--name", "combined", "alpha", "beta")
        m = self.meta_of("combined")
        self.assertEqual(m["scope"], "full")
        self.assertEqual(m["parent"], self.meta_of("alpha")["id"])   # first source
        self.assertEqual(sorted(m["tags"]), ["auth", "perf"])

    def test_merge_needs_two_sources(self):
        code, _ = self.cli("merge", "--name", "x", "alpha")
        self.assertEqual(code, 2)

    def test_merge_dedups_repeated_source(self):
        # alpha listed twice + beta -> alpha is folded in exactly once
        code, _ = self.cli("merge", "--name", "c", "alpha", "alpha", "beta")
        self.assertEqual(code, 0)
        self.assertEqual(self.body_of("c").count('## From "alpha"'), 1)

    def test_merge_two_of_the_same_is_rejected(self):
        # the same note twice is <2 DISTINCT sources -> rejected, not a self-merge
        code, _ = self.cli("merge", "--name", "c", "alpha", "alpha")
        self.assertEqual(code, 2)

    def test_merge_missing_source_is_reported(self):
        code, out = self.cli("merge", "--name", "x", "alpha", "ghost")
        self.assertEqual(code, 0)                 # graceful (No note ...)
        self.assertIn("No note matches", out)

    # ---- diff -------------------------------------------------------------
    def test_diff_sections_and_pointers(self):
        code, out = self.cli("diff", "--json", "alpha", "beta")
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertIn("Decisions", d["sections_only_in_a"])
        self.assertIn("Open questions / assumptions", d["sections_only_in_b"])
        # shared section + shared pointer detected
        self.assertIn("Summary", d["sections_common"])
        self.assertTrue(any("src/mw.py" in p for p in d["pointers_common"]))
        self.assertTrue(any("src/auth.py" in p for p in d["pointers_only_in_a"]))
        self.assertTrue(any("src/limit.py" in p for p in d["pointers_only_in_b"]))
        self.assertTrue(d["summary_changed"])

    def test_diff_human_output(self):
        code, out = self.cli("diff", "alpha", "beta")
        self.assertEqual(code, 0)
        self.assertIn("diff:", out)
        self.assertIn("Decisions", out)

    def test_diff_identical_note_against_itself(self):
        code, out = self.cli("diff", "--json", "alpha", "alpha")
        d = json.loads(out)
        self.assertEqual(d["sections_only_in_a"], [])
        self.assertEqual(d["sections_only_in_b"], [])
        self.assertFalse(d["summary_changed"])


class SectionParsingCase(unittest.TestCase):
    """Fence-aware section helpers used by merge/diff (regression for the review)."""

    def test_section_lines_ignore_fenced_headers(self):
        body = ("## Summary\nx\n\n## Files & areas to look at\n- real.py — real\n\n"
                "## Example\n```\n## Files & areas to look at\n- fake.py — fenced\n```\n\n"
                "## Next step\ndone\n")
        ptrs = " ".join(cairn._section_lines(body, "Files & areas to look at"))
        self.assertIn("real.py", ptrs)
        self.assertNotIn("fake.py", ptrs)          # the fenced fake pointer is ignored

    def test_section_headers_ignore_fenced_headers(self):
        body = ("## Summary\nx\n\n## Example\n```\n## Secret Section\n- y\n```\n\n"
                "## Next step\ndone\n")
        heads = cairn._section_headers(body)
        self.assertIn("Example", heads)
        self.assertNotIn("Secret Section", heads)  # header inside a fence is not a section

    def test_section_lines_handle_duplicate_headers(self):
        body = ("## Files & areas to look at\n- a.py\n\n"
                "## Other\nz\n\n## Files & areas to look at\n- b.py\n")
        ptrs = " ".join(cairn._section_lines(body, "Files & areas to look at"))
        self.assertIn("a.py", ptrs)
        self.assertIn("b.py", ptrs)                # BOTH occurrences harvested

    def test_demote_headers_skips_code_fences(self):
        body = "## Title\ntext\n```\n# a code comment\n```\n"
        out = cairn._demote_headers(body)
        self.assertIn("### Title", out)            # real header demoted
        self.assertIn("# a code comment", out)     # fenced comment untouched
        self.assertNotIn("## a code comment", out)

    def test_no_space_header_is_consistent(self):
        # '##Files' (no space) is NOT a header for any helper -> consistent views
        body = "##Files & areas to look at\n- x.py\n\n## Real\nz\n"
        self.assertEqual(cairn._section_lines(body, "Files & areas to look at"), [])
        self.assertNotIn("Files & areas to look at", cairn._section_headers(body))


if __name__ == "__main__":
    unittest.main()
