"""
activation.py
Sistema de activación de licencias para Nexar Finanzas.

Soporta dos sistemas en paralelo:

  SISTEMA NUEVO — Token Base64 + RSA (clientes nuevos desde v2.0)
    El generador de licencias produce un Token Base64 que contiene
    el payload firmado con RSA (PKCS1v15 + SHA256). La app verifica
    la firma con la clave pública embebida sin necesidad de internet.

  SISTEMA LEGACY — HMAC-SHA256 (códigos XXXX-XXXX-XXXX-XXXX existentes)
    Los clientes que ya activaron con el sistema anterior siguen
    funcionando. Al validar, quedan registrados como tier=BASICA.
    No se generan nuevos códigos HMAC.

Flujo de activación en routes.py /activate:
  Token Base64  → activar_token_rsa()  → guarda tier + expires_at en BD
  Código HMAC   → detect_license_type() → guarda tier=BASICA en BD
"""

import hmac
import json
import base64
import hashlib
import sqlite3
from datetime import date, datetime


# ─── Clave pública RSA embebida ───────────────────────────────────────────────
#
# Misma clave que keys/public_key.pem del proyecto.
# Embebida aquí para que la verificación funcione sin depender de la ruta
# del archivo en instalaciones portables o compiladas con PyInstaller.
#
_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApLcG8Uq6+sV4E1mlWY5z
zZC8H2i4EM0s2jGq8XCcVOJipamw+1rvzHSoAjgmtnJCw8+218yR3PXK90NqSguO
9blAfsxswwtlid9RxwPQ1y8jU1LuZd65DeowgGtu+4lrNjeIZqmesarPbgOIMZ3q
PZpurtOUjy74moR5pwGIPQk9TLl685MeyYcDdV9UO0uiiYyxS+yopRvvOrhXJlH0
C5I+KeCqjOLXglTXOXoYFXOUXwWajT/FFjXHabWO/yCA8igXqn+rdt+bPoLBfmYk
0FjjYn2HrwRB8NZ4Lv4pQc30EukM32Nyri80Dak8/dtjNLPrc0wTzAvqeyUDHHKu
dQIDAQAB
-----END PUBLIC KEY-----"""


def _cargar_clave_publica():
    """Carga la clave pública RSA desde la constante embebida."""
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_public_key(_PUBLIC_KEY_PEM)


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA NUEVO — Token Base64 + RSA
# ═══════════════════════════════════════════════════════════════════════════════

def validar_token_rsa(token_b64: str) -> tuple:
    """
    Valida un token Base64 generado por el generador de licencias FH.

    Proceso:
      1. Decodificar Base64 → JSON con campos públicos + firma
      2. Reconstruir el payload con los mismos campos (sort_keys=True)
         CRÍTICO: orden idéntico al generador en license_manager.py
      3. Verificar firma RSA (PKCS1v15 + SHA256) con la clave pública
      4. Verificar que product == 'fh'
      5. Verificar hardware_id == este equipo

    Retorna: (ok: bool, mensaje: str, data: dict | None)
    """
    try:
        # Paso 1: decodificar token
        try:
            raw  = base64.b64decode(token_b64.strip())
            data = json.loads(raw.decode('utf-8'))
        except Exception:
            return False, "Token inválido: no se pudo decodificar.", None

        # Paso 2: verificar que es para FH
        if data.get("product") != "fh":
            return False, "Este token no corresponde a Nexar Finanzas.", None

        # Paso 3: reconstruir payload para verificar firma
        # ATENCIÓN: campos y orden DEBEN ser idénticos a create_fh_license()
        # en license_manager.py del generador. Si se agregan campos allá,
        # hay que actualizarlos acá también.
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

        # Paso 4: verificar firma RSA
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            public_key = _cargar_clave_publica()
            firma_bytes = bytes.fromhex(firma_hex)
            public_key.verify(
                firma_bytes,
                payload_str.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except ImportError:
            return False, (
                "No se encontró la librería 'cryptography'. "
                "Ejecutá: pip install cryptography"
            ), None
        except Exception:
            return False, "Firma digital inválida. El token fue alterado o es incorrecto.", None

        # Paso 5: verificar hardware_id
        from licensing.hardware_id import get_hardware_id
        hw_local = get_hardware_id()
        hw_token = data.get("hardware_id", "")

        if hw_token != hw_local:
            return False, (
                "Este token fue generado para otro equipo. "
                "Solicitá un nuevo token con tu ID de máquina actual."
            ), None

        return True, "Token válido.", data

    except Exception as e:
        return False, f"Error inesperado al validar el token: {str(e)[:80]}", None


def activar_token_rsa(token_b64: str, db_path: str) -> tuple:
    """
    Valida el token y si es correcto guarda la activación en la BD.

    Retorna: (ok: bool, mensaje: str, tier: str | None)

    Lógica de activación PRO sobre BASICA:
      - Si tier=PRO y NO hay BASICA previa → error (debe activar BASICA primero)
      - Si tier=PRO y HAY BASICA previa    → activa PRO correctamente
      - Si tier=BASICA                     → activa normalmente
    """
    ok, msg, data = validar_token_rsa(token_b64)
    if not ok:
        return False, msg, None

    tier       = data.get("tier", "BASICA")
    expires_at = data.get("expires_at") or ""

    # Verificar que PRO tenga BASICA previa
    if tier == "PRO":
        try:
            conn     = sqlite3.connect(db_path)
            tier_row = conn.execute(
                "SELECT value FROM config WHERE key='license_tier'"
            ).fetchone()
            conn.close()
            tier_actual = tier_row[0] if tier_row else "DEMO"
        except Exception:
            tier_actual = "DEMO"

        if tier_actual not in ("BASICA", "PRO"):
            return False, (
                "Para activar el Plan Pro primero necesitás activar el Plan Básico. "
                "Si recibiste dos tokens, activá primero el token BÁSICO."
            ), None

    # Guardar activación en BD
    _guardar_activacion_bd(
        db_path       = db_path,
        license_key   = data.get("license_key", ""),
        tier          = tier,
        expires_at    = expires_at,
        license_type  = data.get("type", ""),
        token_b64     = token_b64,
    )

    if tier == "PRO":
        if expires_at:
            msg = f"Plan Pro activado. Vence el {expires_at}."
        else:
            msg = "Plan Pro activado."
    else:
        msg = "Plan Básico activado. Acceso permanente habilitado."

    return True, msg, tier


def _guardar_activacion_bd(db_path: str, license_key: str, tier: str,
                            expires_at: str, license_type: str,
                            token_b64: str = "") -> None:
    """
    Persiste en la BD los datos de una activación exitosa.
    Usado tanto por el sistema RSA nuevo como por la migración HMAC legacy.
    """
    conn = sqlite3.connect(db_path)
    ahora = datetime.now().isoformat()

    configs = {
        'version':          'FULL',
        'license_tier':     tier,
        'license_expires_at': expires_at,
        'license_key':      license_key,
        'license_type':     license_type,
        'license_activated_at': ahora,
    }
    if token_b64:
        configs['license_token_b64'] = token_b64

    for key, value in configs.items():
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA LEGACY — HMAC-SHA256 (códigos XXXX-XXXX-XXXX-XXXX)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Este sistema NO genera nuevos códigos.
# Solo se mantiene para validar códigos existentes de clientes anteriores.
# Al validar, se registra tier=BASICA (equivalencia de plan).
#

# ⚠️ CLAVE SECRETA LEGACY — NO MODIFICAR (rompe compatibilidad con códigos existentes)
_SECRET_KEY = b"NexarFinanzas2026_RolandoNavarta_SecretKey_X9Z"


def _compute_hmac(seed: str) -> str:
    """Calcula HMAC-SHA256 y lo codifica en Base32."""
    h = hmac.new(_SECRET_KEY, seed.encode('utf-8'), hashlib.sha256)
    digest = base64.b32encode(h.digest())[:16].decode('utf-8').upper()
    return f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"


def generate_permanent_code() -> str:
    """[LEGACY] Genera el código permanente universal."""
    return _compute_hmac("FINANZAS_FULL_PERMANENT_ACTIVATION")


def generate_monthly_code(year: int, month: int) -> str:
    """[LEGACY] Genera código válido para un mes específico."""
    return _compute_hmac(f"MONTHLY_{year:04d}_{month:02d}")


def generate_client_code(client_id: str) -> str:
    """[LEGACY] Genera código para un cliente específico."""
    cid  = client_id.strip().upper()[:4].ljust(4, '0')
    seed = f"CLIENT_{cid}_FINANZAS"
    h    = hmac.new(_SECRET_KEY, seed.encode('utf-8'), hashlib.sha256)
    digest = base64.b32encode(h.digest())[:12].decode('utf-8').upper()
    return f"{cid}-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


def validate_activation_code(code: str) -> bool:
    """
    [LEGACY] Valida un código HMAC offline.
    Firma idéntica al original para compatibilidad con routes.py.
    """
    return detect_license_type(code) is not None


def detect_license_type(code: str) -> dict | None:
    """
    [LEGACY] Detecta y valida códigos HMAC.

    Firma idéntica al original para compatibilidad con routes.py.
    Retorna dict con 'tipo', 'vencimiento', 'descripcion' o None si inválido.

    Al activar con código HMAC, routes.py llama a _guardar_activacion()
    que ahora graba tier=BASICA además de los campos de compatibilidad.
    """
    code = code.strip().upper().replace(' ', '')

    # 1. Código permanente
    if code == generate_permanent_code():
        return {
            'tipo':        'permanente',
            'vencimiento': None,
            'descripcion': 'Licencia permanente — sin vencimiento',
        }

    # 2. Código mensual: mes actual ± 2 meses de gracia
    today = date.today()
    for delta in [-1, 0, 1, 2]:
        m = today.month + delta
        y = today.year
        if m < 1:  m += 12; y -= 1
        if m > 12: m -= 12; y += 1
        if code == generate_monthly_code(y, m):
            import calendar
            mes_codigo  = today.month + delta
            anio_codigo = today.year
            if mes_codigo < 1:  mes_codigo += 12; anio_codigo -= 1
            if mes_codigo > 12: mes_codigo -= 12; anio_codigo += 1
            ultimo_dia = calendar.monthrange(anio_codigo, mes_codigo)[1]
            venc = date(anio_codigo, mes_codigo, ultimo_dia)
            meses_es = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                        'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
            return {
                'tipo':        'mensual',
                'vencimiento': venc.isoformat(),
                'descripcion': (
                    f'Licencia mensual — vence el {ultimo_dia} de '
                    f'{meses_es[mes_codigo-1]} de {anio_codigo}'
                ),
            }

    # 3. Código de cliente
    parts = code.split('-')
    if len(parts) == 4:
        client_id = parts[0]
        if code == generate_client_code(client_id):
            return {
                'tipo':        'cliente',
                'vencimiento': None,
                'descripcion': f'Licencia cliente #{client_id} — sin vencimiento',
            }

    return None
