import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN — completar una sola vez
# ─────────────────────────────────────────────────────────────────────────────
# Pegá aquí el ID del index.json que aparece en el Generador de Licencias
# la primera vez que creás una licencia para un cliente.
#
# Pasos:
#   1. Abrí el Generador de Licencias y generá la primera licencia.
#   2. Copiá el valor del campo "ID del index.json en Drive".
#   3. Pegalo como valor de DRIVE_INDEX_FILE_ID abajo.
#   4. Asegurate de que index.json en Drive tenga acceso
#      "Cualquiera con el enlace puede ver".
# ─────────────────────────────────────────────────────────────────────────────
DRIVE_INDEX_FILE_ID = "1xmVhdMhHfI_a3631pT1aoYGA9qeDzmex"

_TIMEOUT = 10   # segundos de espera máxima por request


def get_license_file_id(license_key):
    """
    Descarga el index.json de Drive y retorna el file_id
    correspondiente a la license_key dada, o None si no existe.
    """

    if DRIVE_INDEX_FILE_ID == "REEMPLAZAR_POR_ID_DEL_INDEX":
        raise RuntimeError(
            "El sistema de licencias RSA no está configurado.\n"
            "Completá DRIVE_INDEX_FILE_ID en licensing/license_api.py"
        )

    url = f"https://drive.google.com/uc?id={DRIVE_INDEX_FILE_ID}&export=download"

    try:
        r = requests.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get(license_key)

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Sin conexion a internet. La activacion con este tipo de codigo "
            "requiere conexion para verificar la licencia."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            "El servidor tardo demasiado en responder. "
            "Verifica tu conexion e intenta nuevamente."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Error al consultar el indice de licencias: {e}")
    except ValueError:
        raise RuntimeError(
            "El indice de licencias tiene un formato inesperado. "
            "Contacta al desarrollador."
        )


def download_license(file_id):
    """
    Descarga el JSON de la licencia pública desde Drive.
    """

    url = f"https://drive.google.com/uc?id={file_id}&export=download"

    try:
        r = requests.get(url, timeout=_TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(
                f"No se pudo descargar la licencia (HTTP {r.status_code})."
            )
        return r.json()

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Sin conexion a internet. Verifica tu red e intenta nuevamente."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            "El servidor tardo demasiado. Intenta nuevamente."
        )
    except ValueError:
        raise RuntimeError(
            "La licencia descargada tiene un formato inesperado. "
            "Contacta al desarrollador."
        )
