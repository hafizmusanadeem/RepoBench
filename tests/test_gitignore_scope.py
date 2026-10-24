"""Task 1: frontend/src/lib must be tracked; runtime data must be ignored."""
import subprocess
import unittest


def check_ignore(path):
    r = subprocess.run(["git", "check-ignore", "-v", path],
                       capture_output=True, text=True)
    return r.returncode == 0


class TestGitignoreScope(unittest.TestCase):
    def test_frontend_lib_tracked(self):
        self.assertFalse(check_ignore("frontend/src/lib/api.ts"))
        self.assertFalse(check_ignore("frontend/src/lib/utils.ts"))

    def test_runtime_data_ignored(self):
        self.assertTrue(check_ignore("backend/data/repobench.db"))
        self.assertTrue(check_ignore("backend/data/sandboxes/abc"))
        self.assertTrue(check_ignore(".env"))


if __name__ == "__main__":
    unittest.main()
