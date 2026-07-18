import os
import unittest
from unittest.mock import patch

import app


class ExternalBrowserTests(unittest.TestCase):
    def test_restores_ld_library_path_from_original_for_pyinstaller_linux(self):
        env = {
            "LD_LIBRARY_PATH": "/opt/NexarFinanzas/_internal",
            "LD_LIBRARY_PATH_ORIG": "/usr/lib/x86_64-linux-gnu",
            "OTHER": "1",
        }

        with patch.object(app.sys, "frozen", True, create=True), patch.object(app.sys, "platform", "linux"):
            clean_env = app._clean_external_process_env(env)

        self.assertEqual(clean_env["LD_LIBRARY_PATH"], "/usr/lib/x86_64-linux-gnu")
        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/NexarFinanzas/_internal")
        self.assertEqual(clean_env["OTHER"], "1")

    def test_removes_ld_library_path_without_original_for_pyinstaller_linux(self):
        env = {
            "LD_LIBRARY_PATH": "/opt/NexarFinanzas/_internal",
            "OTHER": "1",
        }

        with patch.object(app.sys, "frozen", True, create=True), patch.object(app.sys, "platform", "linux"):
            clean_env = app._clean_external_process_env(env)

        self.assertNotIn("LD_LIBRARY_PATH", clean_env)
        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/NexarFinanzas/_internal")
        self.assertEqual(clean_env["OTHER"], "1")

    def test_uses_xdg_open_on_linux(self):
        with (
            patch.object(app.sys, "platform", "linux"),
            patch.object(app.subprocess, "Popen") as mock_popen,
        ):
            opened = app.open_external_url("http://127.0.0.1:5000")

        self.assertTrue(opened)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], ["xdg-open", "http://127.0.0.1:5000"])
        self.assertTrue(kwargs["start_new_session"])
        self.assertIn("env", kwargs)

    def test_falls_back_when_xdg_open_is_missing(self):
        with (
            patch.object(app.sys, "platform", "linux"),
            patch.object(app.subprocess, "Popen", side_effect=FileNotFoundError),
            patch.object(app.webbrowser, "open", return_value=True) as mock_webbrowser_open,
        ):
            opened = app.open_external_url("http://127.0.0.1:5000")

        self.assertTrue(opened)
        mock_webbrowser_open.assert_called_once_with("http://127.0.0.1:5000")

    def test_does_not_mutate_process_environment(self):
        before = dict(os.environ)

        with (
            patch.dict(os.environ, {"LD_LIBRARY_PATH": "/opt/NexarFinanzas/_internal"}, clear=False),
            patch.object(app.sys, "frozen", True, create=True),
            patch.object(app.sys, "platform", "linux"),
            patch.object(app.subprocess, "Popen"),
        ):
            current_before = dict(os.environ)
            opened = app.open_external_url("http://127.0.0.1:5000")
            current_after = dict(os.environ)

        self.assertTrue(opened)
        self.assertEqual(current_after, current_before)
        self.assertEqual(dict(os.environ), before)
