import shutil
from pathlib import Path
from uuid import uuid4


_TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_tests"
_TEST_TMP_ROOT.mkdir(exist_ok=True)


class TempDirCompat:
    def __init__(self):
        path = _TEST_TMP_ROOT / f"tmp-{uuid4().hex}"
        path.mkdir(parents=True, exist_ok=False)
        self.name = str(path)

    def cleanup(self):
        shutil.rmtree(self.name, ignore_errors=True)


def make_temp_dir():
    return TempDirCompat()
