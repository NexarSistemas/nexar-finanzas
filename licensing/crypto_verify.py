
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


def verify_signature(license_data):

    signature = license_data["signature"]
    payload_data = dict(license_data)
    payload_data.pop("signature")

    payload = json.dumps(payload_data, sort_keys=True)

    with open("finanzashogar/keys/public_key.pem", "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    public_key.verify(
        bytes.fromhex(signature),
        payload.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    return True
