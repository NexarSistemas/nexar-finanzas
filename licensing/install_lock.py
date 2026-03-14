import hashlib
import os
from pathlib import Path

from .license_storage import (
    get_install_lock_file,
    save_json,
    load_json,
)


def generate_install_hash(hardware_id, license_key):
    """
    Genera hash único de instalación.
    """

    install_path = str(Path(os.getcwd()).resolve())

    raw = f"{hardware_id}:{license_key}:{install_path}"

    return hashlib.sha256(raw.encode()).hexdigest()


def create_install_lock(license_key, hardware_id):
    """
    Crea el archivo install.lock
    """

    lock_file = get_install_lock_file()

    install_hash = generate_install_hash(
        hardware_id,
        license_key
    )

    data = {
        "license_key": license_key,
        "hardware_id": hardware_id,
        "install_hash": install_hash
    }

    save_json(lock_file, data)


def validate_install_lock(license_key, hardware_id):
    """
    Verifica que el programa no haya sido copiado.
    """

    lock_file = get_install_lock_file()

    data = load_json(lock_file)

    if not data:
        return False

    if data["license_key"] != license_key:
        return False

    if data["hardware_id"] != hardware_id:
        return False

    expected_hash = generate_install_hash(
        hardware_id,
        license_key
    )

    if data["install_hash"] != expected_hash:
        return False

    return True