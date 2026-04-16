import sys
import os
# Añadir el path del SDK si no está instalado como paquete
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'nexar_licencias')))
from nexar_licencias import validar_licencia

def verificar_licencia_finanzas(licencia, public_key):
    """
    Punto de entrada para Finanzas usando el nuevo SDK de Supabase.
    """
    return validar_licencia(
        licencia_dict=licencia,
        public_key=public_key,
        product_name="finanzas",
        debug=True
    )

# Eliminamos las funciones antiguas de Drive (get_license_file_id, download_license)
# ya que Supabase maneja la entrega de datos directamente.
