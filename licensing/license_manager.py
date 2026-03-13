
from datetime import datetime

from .hardware_id import get_hardware_id
from .crypto_verify import verify_signature
from .license_api import get_license_file_id, download_license
from .license_storage import save_license, load_license, license_exists
from .demo_state import set_demo, set_full


def activate_license(license_key):

    file_id = get_license_file_id(license_key)

    if not file_id:
        raise Exception("Licencia no encontrada")

    license_data = download_license(file_id)

    verify_signature(license_data)

    hardware = get_hardware_id()

    if license_data["hardware_id"] != hardware:
        raise Exception("Licencia pertenece a otra máquina")

    save_license(license_data)

    set_full(license_data)


def validate_local_license():

    if not license_exists():
        set_demo()
        return False

    license_data = load_license()

    try:
        verify_signature(license_data)
    except Exception:
        set_demo()
        return False

    hw = get_hardware_id()

    if license_data["hardware_id"] != hw:
        set_demo()
        return False

    if "expires_at" in license_data:

        expires = datetime.fromisoformat(license_data["expires_at"])

        if datetime.now() > expires:
            set_demo()
            return False

    set_full(license_data)

    return True
