import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# Ruta absoluta a la clave pública, relativa a este archivo
_PUBLIC_KEY_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keys', 'public_key.pem')
)


def verify_signature(license_data):
    """
    Verifica la firma RSA de una licencia pública.

    La firma fue calculada sobre los campos:
        hardware_id, license_key, max_machines, type
    serializados con json.dumps(..., sort_keys=True).

    Lanza Exception si la firma es inválida.
    """

    signature = license_data.get("signature")
    if not signature:
        raise ValueError("La licencia no contiene firma.")

    # Reconstruir exactamente el payload que firmó el generador
    payload_data = {
        "hardware_id":  license_data["hardware_id"],
        "license_key":  license_data["license_key"],
        "max_machines": license_data["max_machines"],
        "type":         license_data["type"],
    }
    payload = json.dumps(payload_data, sort_keys=True)

    with open(_PUBLIC_KEY_PATH, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    # Lanza InvalidSignature si la firma no coincide
    public_key.verify(
        bytes.fromhex(signature),
        payload.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    return True
