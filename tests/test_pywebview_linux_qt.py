import unittest
from unittest.mock import patch

import app


class PywebviewStartBackendTests(unittest.TestCase):
    def test_linux_uses_qt_backend(self):
        with patch.object(app.sys, "platform", "linux"):
            kwargs = app._pywebview_start_kwargs()

        self.assertEqual(kwargs["gui"], "qt")
        self.assertFalse(kwargs["debug"])
        self.assertFalse(kwargs["http_server"])

    def test_windows_keeps_default_backend_selection(self):
        with patch.object(app.sys, "platform", "win32"):
            kwargs = app._pywebview_start_kwargs()

        self.assertNotIn("gui", kwargs)
        self.assertFalse(kwargs["debug"])
        self.assertFalse(kwargs["http_server"])
