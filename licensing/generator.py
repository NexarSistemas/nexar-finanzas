import json
import base64
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# Configuración de Supabase (Deben coincidir con tu .env)
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "tu-service-role-key" # Usar service role para escritura

def generar_y_subir_licencia(private_key_pem, license_data):
    """
    1. Firma los datos de la licencia.
    2. Genera el token Base64 para el cliente.
    3. Sube la licencia a Supabase.
    """
    
    # Cargar clave privada
    priv_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None
    )

    # Ordenar y serializar payload para firmar (sin la firma)
    message = json.dumps(license_data, sort_keys=True).encode()
    
    # Firmar
    signature = priv_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    sig_hex = signature.hex()
    license_data['public_signature'] = sig_hex

    # Token para el cliente (Base64 del JSON completo)
    token_cliente = base64.b64encode(json.dumps(license_data).encode()).decode()

    # Subir a Supabase
    url = f"{SUPABASE_URL}/rest/v1/licencias"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Mapeo de campos para la tabla de Supabase
    db_payload = {
        "license_key": license_data['license_key'],
        "product": license_data['product'],
        "tier": license_data.get('tier', 'BASICA'),
        "expires_at": license_data.get('expires_at'),
        "public_signature": sig_hex,
        "raw_data": license_data # Guardamos todo el objeto por seguridad
    }

    response = requests.post(url, headers=headers, json=db_payload)
    
    if response.status_code in [201, 200]:
        print("✅ Licencia generada y subida a Supabase.")
        print(f"🔑 TOKEN PARA EL CLIENTE:\n{token_cliente}")
        return token_cliente
    else:
        print(f"❌ Error al subir a Supabase: {response.text}")
        return None