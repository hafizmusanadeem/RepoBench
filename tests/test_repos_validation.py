"""Task 2: repo URL/ref validation, cache id stability, unknown-language profile."""
import unittest
from pathlib import Path

from backend import repos
from backend.profiler import profile_repo
from backend.schemas import Profile


class TestRepoValidation(unittest.TestCase):
    def test_valid_urls_accepted(self):
        for url in ("https://github.com/o/r.git", "https://github.com/o/r",
                    "ssh://git@github.com/o/r.git", "git@github.com:o/r.git"):
            self.assertTrue(repos._URL_RE.match(url), url)

    def test_invalid_schemes_rejected(self):
        for url in ("http://github.com/o/r.git", "file:///etc/passwd",
                    "/etc/passwd", "ftp://x/y.git"):
            self.assertIsNone(repos._URL_RE.match(url), url)
            with self.assertRaises(ValueError, msg=url):
                repos.register_repo(url, None)

    def test_bad_ref_rejected(self):
        for ref in ("-evil", "../escape", "a b", "semi;colon"):
            with self.assertRaises(ValueError, msg=ref):
                repos.register_repo("https://github.com/o/r.git", ref)

    def test_repo_id_stable(self):
        self.assertEqual(repos.repo_id_for("https://github.com/o/r", "main"),
                         repos.repo_id_for("https://github.com/o/r", "main"))
        self.assertNotEqual(repos.repo_id_for("https://github.com/o/r", "main"),
                            repos.repo_id_for("https://github.com/o/r", "dev"))

    def test_unknown_language_profile(self):
        p = Profile(**profile_repo(Path("/nonexistent-xyz-dir")))
        self.assertEqual(p.language, "unknown")
        self.assertEqual(p.test_command, "")
        self.assertTrue(p.notes)

    def test_profile_has_build_lint_fields(self):
        p = Profile()
        self.assertEqual(p.build_command, "")
        self.assertEqual(p.lint_command, "")


if __name__ == "__main__":
    unittest.main()
