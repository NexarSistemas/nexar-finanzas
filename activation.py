"""
activation.py
Sistema de activación de licencia offline usando HMAC-SHA256.
Genera y valida códigos de activación sin necesidad de conexión a internet.
"""

import hmac
import hashlib
import base64
from datetime import date

# ⚠️ CLAVE SECRETA - NO COMPARTIR NI MODIFICAR (rompe compatibilidad de códigos)
_SECRET_KEY = b"FinanzasHogar2026_RolandoNavarta_SecretKey_X9Z"


def _compute_hmac(seed: str) -> str:
    """Calcula HMAC-SHA256 y lo codifica en Base32 (solo letras y números)."""
    h = hmac.new(_SECRET_KEY, seed.encode('utf-8'), hashlib.sha256)
    digest = base64.b32encode(h.digest())[:16].decode('utf-8').upper()
    return f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"


def generate_permanent_code() -> str:
    """Genera el código permanente universal."""
    return _compute_hmac("FINANZAS_FULL_PERMANENT_ACTIVATION")


def generate_monthly_code(year: int, month: int) -> str:
    """Genera código válido para un mes específico."""
    return _compute_hmac(f"MONTHLY_{year:04d}_{month:02d}")


def generate_client_code(client_id: str) -> str:
    """
    Genera código para un cliente específico.
    client_id: string de hasta 8 chars (ej: '0001', 'JUAN', 'CLI001')
    Formato del código: CLIE-XXXX-XXXX-XXXX donde CLIE identifica al cliente.
    """
    cid = client_id.strip().upper()[:4].ljust(4, '0')
    seed = f"CLIENT_{cid}_FINANZAS"
    h = hmac.new(_SECRET_KEY, seed.encode('utf-8'), hashlib.sha256)
    digest = base64.b32encode(h.digest())[:12].decode('utf-8').upper()
    return f"{cid}-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


def validate_activation_code(code: str) -> bool:
    """
    Valida un código de activación completamente offline.
    Intenta múltiples estrategias de validación.
    """
    return detect_license_type(code) is not None


def detect_license_type(code: str) -> dict | None:
    """
    Detecta el tipo de licencia del código.
    Retorna dict con 'tipo', 'vencimiento' (o None si es permanente), 'descripcion'
    o None si el código es inválido.
    """
    code = code.strip().upper().replace(' ', '')

    # 1. Código permanente
    if code == generate_permanent_code():
        return {
            'tipo':        'permanente',
            'vencimiento': None,
            'descripcion': 'Licencia permanente — sin vencimiento',
        }

    # 2. Código mensual: mes actual ± 1 mes de gracia
    today = date.today()
    for delta in [-1, 0, 1, 2]:
        m = today.month + delta
        y = today.year
        if m < 1:
            m += 12; y -= 1
        if m > 12:
            m -= 12; y += 1
        if code == generate_monthly_code(y, m):
            # Vencimiento: último día del mes que corresponde al código
            import calendar
            # Usar el mes del código (delta=0 es el mes actual)
            mes_codigo = today.month + delta
            anio_codigo = today.year
            if mes_codigo < 1:
                mes_codigo += 12; anio_codigo -= 1
            if mes_codigo > 12:
                mes_codigo -= 12; anio_codigo += 1
            ultimo_dia = calendar.monthrange(anio_codigo, mes_codigo)[1]
            venc = date(anio_codigo, mes_codigo, ultimo_dia)
            meses_es = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                        'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
            return {
                'tipo':        'mensual',
                'vencimiento': venc.isoformat(),
                'descripcion': f'Licencia mensual — vence el {ultimo_dia} de {meses_es[mes_codigo-1]} de {anio_codigo}',
            }

    # 3. Código de cliente
    parts = code.split('-')
    if len(parts) == 4:
        client_id = parts[0]
        expected = generate_client_code(client_id)
        if code == expected:
            return {
                'tipo':        'cliente',
                'vencimiento': None,
                'descripcion': f'Licencia cliente #{client_id} — sin vencimiento',
            }

    return None
