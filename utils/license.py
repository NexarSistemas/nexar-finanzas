import json
import os
import hashlib
from datetime import datetime

RUTA_LICENSE = "license.key"

ESTADOS = {
    "VALIDA": "VALIDA",
    "INVALIDA": "INVALIDA",
    "VENCIDA": "VENCIDA",
    "NO_ENCONTRADA": "NO_ENCONTRADA"
}


def cargar_licencia():
    if not os.path.exists(RUTA_LICENSE):
        return None

    try:
        with open(RUTA_LICENSE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def generar_firma(clave, producto, expira):
    data = f"{clave}{producto}{expira}"
    return hashlib.sha256(data.encode()).hexdigest()


def validar_integridad(licencia):
    firma_calculada = generar_firma(
        licencia.get("clave"),
        licencia.get("producto"),
        licencia.get("expira")
    )

    return firma_calculada == licencia.get("firma")


def validar_expiracion(expira):
    if not expira:
        return True  # sin expiración

    try:
        fecha_exp = datetime.strptime(expira, "%Y-%m-%d")
        return datetime.now() <= fecha_exp
    except Exception:
        return False


def validar_producto(licencia, producto_actual):
    return licencia.get("producto") == producto_actual


def validar_licencia(producto_actual="nexar"):
    licencia = cargar_licencia()

    if not licencia:
        return ESTADOS["NO_ENCONTRADA"], "Licencia no encontrada"

    # Integridad
    if not validar_integridad(licencia):
        return ESTADOS["INVALIDA"], "Licencia alterada"

    # Producto
    if not validar_producto(licencia, producto_actual):
        return ESTADOS["INVALIDA"], "Licencia no válida para este producto"

    # Expiración
    if not validar_expiracion(licencia.get("expira")):
        return ESTADOS["VENCIDA"], "Licencia vencida"

    return ESTADOS["VALIDA"], "Licencia válida"