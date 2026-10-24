"""Task 1: Profile.base_image allowlist for the generated Dockerfile FROM line."""
import unittest

from pydantic import ValidationError

from backend.schemas import Profile


class TestBaseImageValidation(unittest.TestCase):
    def test_accepts_common_images(self):
        for img in ("ubuntu:24.04", "python:3.12-slim",
                    "node:22-bookworm-slim", "golang:1.23-bookworm"):
            self.assertEqual(Profile(base_image=img).base_image, img)

    def test_rejects_injection(self):
        for bad in ("ubuntu\nRUN evil", "ubuntu:24.04\r\nEVIL", "a b",
                    "x;echo hi", "$(id)", "img`id`", "img|tee", ""):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                Profile(base_image=bad)


if __name__ == "__main__":
    unittest.main()
