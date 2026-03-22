
import json
import os
from pathlib import Path

APP_DIR = Path.home() / ".nexarfinanzas"
LICENSE_FILE = APP_DIR / "license.json"


def ensure_dir():
    APP_DIR.mkdir(exist_ok=True)


def save_license(data):
    ensure_dir()
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f)


def load_license():
    if not LICENSE_FILE.exists():
        return None

    with open(LICENSE_FILE) as f:
        return json.load(f)


def license_exists():
    return LICENSE_FILE.exists()
