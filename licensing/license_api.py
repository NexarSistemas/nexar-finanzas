
import requests

# REEMPLAZAR POR EL ID REAL DEL ARCHIVO index.json EN DRIVE
INDEX_URL = "https://drive.google.com/uc?id=REEMPLAZAR_INDEX_ID"


def get_license_file_id(license_key):

    r = requests.get(INDEX_URL)
    data = r.json()

    return data.get(license_key)


def download_license(file_id):

    url = f"https://drive.google.com/uc?id={file_id}"

    r = requests.get(url)

    if r.status_code != 200:
        raise Exception("No se pudo descargar licencia")

    return r.json()
