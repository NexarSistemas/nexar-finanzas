import unittest
from pathlib import Path


class BuildWorkflowPackagingTests(unittest.TestCase):
    def test_final_artifact_search_is_depth_limited_and_validated(self):
        workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("-mindepth 2", workflow)
        self.assertIn("-maxdepth 2", workflow)
        self.assertIn("base_library.zip", workflow)
        self.assertIn("archivo inesperado en el artifact final", workflow)
        self.assertNotIn("find artifacts -type f", workflow)


if __name__ == "__main__":
    unittest.main()
