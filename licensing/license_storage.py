import os
import platform
from pathlib import Path
import json


APP_DIR_NAME = "FinanzasHogar"


def get_app_data_dir():
    """
    Devuelve la carpeta donde se guardan
    licencias y datos locales de la app.
    """

    system = platform.system()

    if system == "Windows":
        base = Path(os.getenv("LOCALAPPDATA"))
    else:
        base = Path.home() / ".local" / "share"

    app_dir = base / APP_DIR_NAME
    app_dir.mkdir(parents=True, exist_ok=True)

    return app_dir


def get_license_file():
    return get_app_data_dir() / "license.json"


def get_install_lock_file():
    return get_app_data_dir() / "install.lock"


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def load_json(path):
    if not path.exists():
        return None

    with open(path, "r") as f:
        return json.load(f)