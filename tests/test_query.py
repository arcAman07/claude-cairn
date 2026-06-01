"""Phase 2 gates: list / find / show behavior, incl. empty + no-match cases."""
import shutil
import tempfile
import unittest

import _util as U


class QueryCase(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cairn-q-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def save(self, name, body, tags="", session="aaaa1111-x", cwd="/proj"):
        argv = ["--store", self.store, "save", "--name", name,
                "--session", session, "--cwd", cwd]
        if tags:
            argv += ["--tags", tags]
        return U.run_cli(argv, stdin_text=body)

    def seed_three(self):
        self.save("auth-jwt", "## Summary\nJWT auth work.\n\n## Directions explored\n"
                  "- Rejected session cookies: need sticky sessions.\n", tags="auth,jwt")
        self.save("db-migration", "## Summary\nMoved to Postgres.\n\n## Decisions\n"
                  "- Chose Postgres over MySQL for JSONB.\n", tags="db,postgres")
        self.save("ui-redesign", "## Summary\nNav redesign.\n\n## Open questions\n"
                  "- Should auth live in the navbar?\n", tags="ui,frontend")


class TestList(QueryCase):
    def test_empty_store(self):
        code, out = U.run_cli(["--store", self.store, "list"])
        self.assertEqual(code, 0)
        self.assertIn("No cairn notes", out)

    def test_list_newest_first(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "list"])
        self.assertEqual(code, 0)
        # ui-redesign saved last -> appears before auth-jwt
        self.assertLess(out.index("ui-redesign"), out.index("auth-jwt"))
        self.assertIn("3 note(s)", out)

    def test_list_json(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "list", "--json"])
        import json
        self.assertEqual(len(json.loads(out)), 3)

    def test_list_project_filter(self):
        self.save("a", "## Summary\nx\n", cwd="/repoA")
        self.save("b", "## Summary\ny\n", cwd="/repoB")
        code, out = U.run_cli(["--store", self.store, "list", "--project", "/repoA"])
        self.assertIn("a", out)
        self.assertNotIn("• b", out)


class TestFind(QueryCase):
    def test_ranks_by_relevance(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "find", "auth"])
        self.assertEqual(code, 0)
        # auth-jwt has "auth" in name+tags+body -> outranks ui-redesign (body only)
        self.assertLess(out.index("auth-jwt"), out.index("ui-redesign"))

    def test_no_match(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "find", "kubernetes"])
        self.assertEqual(code, 0)
        self.assertIn("No notes match", out)

    def test_multi_token(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "find", "postgres jsonb"])
        self.assertIn("db-migration", out)

    def test_find_json_has_scores(self):
        self.seed_three()
        code, out = U.run_cli(["--store", self.store, "find", "auth", "--json"])
        import json
        data = json.loads(out)
        self.assertTrue(all("score" in d for d in data))
        self.assertGreater(data[0]["score"], 0)


class TestShow(QueryCase):
    def test_show_prints_body(self):
        self.save("notable", "## Summary\nUNIQUE_MARKER_TEXT here.\n")
        code, out = U.run_cli(["--store", self.store, "show", "notable"])
        self.assertEqual(code, 0)
        self.assertIn("UNIQUE_MARKER_TEXT", out)
        self.assertIn("# notable", out)

    def test_show_missing_is_safe(self):
        code, out = U.run_cli(["--store", self.store, "show", "ghost"])
        self.assertEqual(code, 0)            # graceful, not an error
        self.assertIn("No note matches", out)

    def test_show_ambiguous_lists_candidates(self):
        self.save("plan-v1", "## Summary\none\n")
        self.save("plan-v2", "## Summary\ntwo\n")
        code, out = U.run_cli(["--store", self.store, "show", "plan"])
        self.assertEqual(code, 2)            # ambiguous -> non-zero, lists options
        self.assertIn("plan-v1", out)
        self.assertIn("plan-v2", out)


if __name__ == "__main__":
    unittest.main()
