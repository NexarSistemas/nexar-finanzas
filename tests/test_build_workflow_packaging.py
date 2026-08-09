import unittest
from pathlib import Path


class BuildWorkflowPackagingTests(unittest.TestCase):
    def test_release_version_sources_match(self):
        version = Path("VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(version, "1.14.0")
        self.assertIn(f"Nexar Finanzas v{version}", Path("README.md").read_text(encoding="utf-8"))
        self.assertIn(f"Nexar Finanzas v{version}", Path("app.py").read_text(encoding="utf-8"))
        self.assertIn(f'APP_VERSION="{version}"', Path("iniciar.sh").read_text(encoding="utf-8"))
        self.assertIn(f"v{version}", Path("iniciar.bat").read_text(encoding="utf-8"))
        self.assertIn(
            f'!define APP_VERSION    "{version}"',
            Path("build_scripts_windows/finanzas_hogar.nsi").read_text(encoding="utf-8"),
        )
        version_info = Path("build_scripts_windows/version_info.txt").read_text(encoding="utf-8")
        self.assertIn("filevers=(1, 14, 0, 0)", version_info)
        self.assertIn("prodvers=(1, 14, 0, 0)", version_info)

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
        self.assertIn("Nexar_Finanzas_macOS_x86_64.zip", build_script)
        self.assertIn("Nexar_Finanzas_macOS_x86_64.dmg", build_script)
        self.assertIn("nexar-finanzas-macos-x86_64-", workflow)
        self.assertIn("target_arch='x86_64'", spec)

    def test_public_release_asset_names_are_stable_and_release_is_tag_only(self):
        workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
        build_sources = "\n".join([
            workflow,
            Path("build_scripts_windows/build.ps1").read_text(encoding="utf-8"),
            Path("build_scripts_windows/installer.iss").read_text(encoding="utf-8"),
            Path("build_scripts_windows/finanzas_hogar.nsi").read_text(encoding="utf-8"),
            Path("build_scripts_linux/build.sh").read_text(encoding="utf-8"),
            Path("build_scripts_macos/build.sh").read_text(encoding="utf-8"),
        ])
        expected_assets = (
            "Nexar_Finanzas_Windows_Setup.exe",
            "Nexar_Finanzas_Windows_Portable.zip",
            "Nexar_Finanzas_Linux_amd64.deb",
            "Nexar_Finanzas_Linux_Portable.tar.gz",
            "Nexar_Finanzas_macOS_x86_64.zip",
            "Nexar_Finanzas_macOS_x86_64.dmg",
        )

        for asset in expected_assets:
            self.assertIn(asset, build_sources)
        self.assertNotIn("NexarFinanzas_v", build_sources)
        self.assertIn('- "v*.*.*"', workflow)
        self.assertIn("github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')", workflow)

    def test_frozen_logging_does_not_write_inside_the_installation(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("log_dir = str(get_user_data_dir())", app_source)
        self.assertNotIn("log_dir = os.path.dirname(sys.executable)", app_source)

    def test_release_notes_awk_regex_is_well_formed(self):
        workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")

        self.assertIn(r"/^## \[/ && found", workflow)
        self.assertNotIn(r"/^## \\[/ && found", workflow)


if __name__ == "__main__":
    unittest.main()
