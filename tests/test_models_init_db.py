import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from models import init_db
from tempdir_compat import make_temp_dir


class InitDbTelemetryIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = make_temp_dir()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = str(Path(self.temp_dir.name) / "init_db.sqlite3")
        previous_testing = os.environ.get("NEXAR_TESTING")
        os.environ["NEXAR_TESTING"] = "1"
        self.addCleanup(self._restore_testing_env, previous_testing)

    @staticmethod
    def _restore_testing_env(previous_value):
        if previous_value is None:
            os.environ.pop("NEXAR_TESTING", None)
        else:
            os.environ["NEXAR_TESTING"] = previous_value

    def _read_demo_install_date(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT value FROM config WHERE key='demo_install_date'"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def test_init_db_does_not_write_telemetry_in_testing_mode(self):
        with patch("models._write_telemetry") as write_telemetry:
            init_db(self.db_path)

        self.assertIsNotNone(self._read_demo_install_date())
        write_telemetry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
