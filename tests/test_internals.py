"""Cover internal defensive paths: slug edges, frontmatter fallback, lock steal."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lib"))
import cairn  # noqa: E402


class TestSlugEdges(unittest.TestCase):
    def test_empty_and_unicode_and_long(self):
        self.assertEqual(cairn.slugify(""), "note")            # empty short-circuit
        self.assertTrue(cairn.slugify("!!!").startswith("note-"))   # punctuation -> hash
        self.assertTrue(cairn.slugify("日本語").startswith("note-"))   # unicode -> hash
        long = cairn.slugify("a" * 200)
        self.assertLessEqual(len(long), 60)


class TestFrontmatterFallback(unittest.TestCase):
    def test_non_json_value_is_tolerated(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "n.md")
            with open(p, "w") as f:
                f.write('---\nname: an unquoted value\ntags: ["a"]\n---\n\nbody\n')
            meta, body = cairn.parse_note(p)
            self.assertEqual(meta["name"], "an unquoted value")  # fell back to raw str
            self.assertEqual(meta["tags"], ["a"])
            self.assertEqual(body.strip(), "body")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestFileLock(unittest.TestCase):
    def test_steals_stale_lock(self):
        d = tempfile.mkdtemp()
        try:
            lockpath = os.path.join(d, "x.lock")
            with open(lockpath, "w") as f:
                f.write("99999")
            old = time.time() - 120
            os.utime(lockpath, (old, old))                 # make it look stale
            lock = cairn.FileLock(lockpath, timeout=2, stale=30)
            with lock:
                self.assertTrue(lock.acquired)             # stole the stale lock
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_proceeds_without_lock_on_timeout(self):
        d = tempfile.mkdtemp()
        try:
            lockpath = os.path.join(d, "y.lock")
            with open(lockpath, "w") as f:                 # fresh (not stale) lock held
                f.write("1")
            lock = cairn.FileLock(lockpath, timeout=0.2, stale=300)
            with lock:
                self.assertFalse(lock.acquired)            # gave up, proceeds anyway
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestStoreDefault(unittest.TestCase):
    def test_default_store_path(self):
        saved = os.environ.pop("CAIRN_HOME", None)
        try:
            self.assertTrue(cairn.store_dir(None).endswith("/.claude/cairn"))
        finally:
            if saved is not None:
                os.environ["CAIRN_HOME"] = saved


if __name__ == "__main__":
    unittest.main()
