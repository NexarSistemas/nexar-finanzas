
import hashlib
import platform
import uuid


def get_hardware_id():
    raw = (
        platform.node()
        + platform.system()
        + platform.machine()
        + str(uuid.getnode())
    )
    return hashlib.sha256(raw.encode()).hexdigest()
