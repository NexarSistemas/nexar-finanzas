"""
activation.py
Sistema de activación de licencias para Nexar Finanzas.
Soporta: Sistema Nuevo (RSA) y Sistema Legacy (HMAC).
"""
import os
import hmac
import json
import base64
import hashlib
import sqlite3
from datetime import date, datetime

# Herramientas de criptografía para el sistema RSA
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    # Definimos excepciones mínimas por si la librería no está instalada
    hashes = serialization = padding = None

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE CLAVE PÚBLICA (RSA)
# ═══════════════════════════════════════════════════════════════════════════════

def get_public_key_text():
    """Obtiene el texto PEM de la llave (Variable de entorno o archivo local)."""
    # 1. Prioridad: Variable de entorno (GitHub Actions / Producción)
    key_data = os.environ.get('PUBLIC_KEY')
    if key_data:
        return key_data
    
    # 2. Segunda opción: Archivo local (Desarrollo)
    key_path = os.path.join("keys", "public_key.pem")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read()
            
    return None

def _cargar_clave_publica():
    """Convierte el texto PEM en un objeto de clave RSA usable."""
    if serialization is None:
        raise ImportError("La librería 'cryptography' no está instalada.")
        
    key_pem = get_public_key_text()
    if not key_pem:
        return None
    
    try:
        return serialization.load_pem_public_key(key_pem.encode('utf-8'))
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA NUEVO — Token Base64 + RSA
# ═══════════════════════════════════════════════════════════════════════════════

def validar_token_rsa(token_b64: str) -> tuple:
    """Valida un token Base64 y verifica su firma digital RSA."""
    try:
        # Paso 1: Decodificar token
        try:
            raw = base64.b64decode(token_b64.strip())
            data = json.loads(raw.decode('utf-8'))
        except Exception:
            return False, "Token inválido: error de formato.", None

        # Paso 2: Verificar producto
        if data.get("product") != "fh":
            return False, "Este token no corresponde a Nexar Finanzas.", None

        # Paso 3: Reconstruir payload para verificar firma
        firma_hex = data.get("public_signature", "")
        if not firma_hex:
            return False, "Token sin firma digital.", None

        payload_dict = {
            "expires_at":  data.get("expires_at"),
            "hardware_id": data.get("hardware_id"),
            "license_key": data.get("license_key"),
            "product":     "fh",
            "tier":        data.get("tier", "BASICA"),
            "type":        data.get("type"),
        }
        payload_str = json.dumps(payload_dict, sort_keys=True)

        # Paso 4: Verificar firma RSA
        public_key = _cargar_clave_publica()
        if not public_key:
            return False, "Error: No se pudo cargar la clave pública de validación.", None

        try:
            firma_bytes = bytes.fromhex(firma_hex)
            public_key.verify(
                firma_bytes,
                payload_str.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception:
            return False, "Firma digital inválida. Token alterado.", None

        # Paso 5: Verificar hardware_id
        from licensing.hardware_id import get_hardware_id
        if data.get("hardware_id") != get_hardware_id():
            return False, "Este token fue generado para otro equipo.", None

        return True, "Token válido.", data

    except Exception as e:
        return False, f"Error: {str(e)[:50]}", None

def activar_token_rsa(token_b64: str, db_path: str) -> tuple:
    """Valida y guarda la activación en la base de datos."""
    ok, msg, data = validar_token_rsa(token_b64)
    if not ok:
        return False, msg, None

    tier = data.get("tier", "BASICA")
    expires_at = data.get("expires_at") or ""

    # Lógica de validación cruzada PRO -> requiere BASICA previa
    if tier == "PRO":
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
            conn.close()
            tier_actual = row[0] if row else "DEMO"
        except:
            tier_actual = "DEMO"

        if tier_actual not in ("BASICA", "PRO"):
            return False, "Para el Plan Pro necesitas activar el Plan Básico primero.", None

    # Guardar en BD
    _guardar_activacion_bd(db_path, data.get("license_key", ""), tier, expires_at, data.get("type", ""), token_b64)
    
    final_msg = f"Plan {tier} activado correctamente."
    if expires_at: final_msg += f" Vence: {expires_at}"
    
    return True, final_msg, tier

def _guardar_activacion_bd(db_path, license_key, tier, expires_at, license_type, token_b64=""):
    conn = sqlite3.connect(db_path)
    ahora = datetime.now().isoformat()
    configs = {
        'version': 'FULL',
        'license_tier': tier,
        'license_expires_at': expires_at,
        'license_key': license_key,
        'license_type': license_type,
        'license_activated_at': ahora,
        'license_token_b64': token_b64
    }
    for k, v in configs.items():
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA LEGACY (HMAC) — Solo para compatibilidad
# ═══════════════════════════════════════════════════════════════════════════════

_SECRET_KEY = b"NexarFinanzas2026_RolandoNavarta_SecretKey_X9Z"

def _compute_hmac(seed: str) -> str:
    h = hmac.new(_SECRET_KEY, seed.encode('utf-8'), hashlib.sha256)
    digest = base64.b32encode(h.digest())[:16].decode('utf-8').upper()
    return f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"

def detect_license_type(code: str) -> dict | None:
    code = code.strip().upper().replace(' ', '')
    # Permanente
    if code == _compute_hmac("FINANZAS_FULL_PERMANENT_ACTIVATION"):
        return {'tipo': 'permanente', 'vencimiento': None, 'descripcion': 'Licencia permanente'}
    
    # Aquí irían las otras validaciones Legacy...
    return None

def validate_activation_code(code: str) -> bool:
    return detect_license_type(code) is not None