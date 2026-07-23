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

    def test_macos_build_is_pinned_to_intel_and_validates_output_architecture(self):
        workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
        build_script = Path("build_scripts_macos/build.sh").read_text(encoding="utf-8")
        spec = Path("build_scripts_macos/nexar_finanzas.spec").read_text(encoding="utf-8")

        self.assertIn("runs-on: macos-15-intel", workflow)
        self.assertNotIn("runs-on: macos-latest", workflow)
        self.assertIn('test "$(uname -m)" = "x86_64"', workflow)
        self.assertIn(
            'test "$(lipo -archs release/NexarFinanzas.app/Contents/MacOS/NexarFinanzas)" = "x86_64"',
            workflow,
        )
        self.assertIn('[[ "$(uname -m)" == "x86_64" ]]', build_script)
        self.assertIn('lipo -archs "$APP_EXECUTABLE"', build_script)
        self.assertIn("target_arch='x86_64'", spec)


if __name__ == "__main__":
    unittest.main()
