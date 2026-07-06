# Revisión remota de templates con Google Stitch

Esta guía prepara Nexar Finanzas para revisar la UI/templates desde una URL web temporal, sin tocar la lógica de negocio ni el empaquetado desktop.

## Objetivo

Permitir que herramientas de diseño como Google Stitch analicen pantallas de Nexar Finanzas usando una URL accesible desde el navegador.

La app sigue siendo Flask + Jinja2 + SQLite. Los scripts npm son solo auxiliares de desarrollo.

## Requisitos

- Python 3.10+
- Node.js 20+ recomendado
- npm
- Dependencias Python instaladas

```bash
python -m pip install -r requirements.txt
npm install
```

## Scripts disponibles

### Modo desktop normal

```bash
npm run dev
```

Ejecuta `python app.py`, mantiene el comportamiento habitual de escritorio con pywebview y fallback al navegador.

### Modo web local

```bash
npm run dev:web
```

Levanta Flask en:

```text
http://127.0.0.1:5000
```

Este modo no abre pywebview. Sirve para revisar templates desde navegador local.

### Modo web remoto

```bash
npm run dev:remote
```

Levanta Flask en:

```text
http://0.0.0.0:5000
```

Esto permite que un túnel externo publique la app temporalmente.

### Túnel temporal

En otra terminal:

```bash
npm run tunnel
```

El comando imprime una URL pública temporal generada por localtunnel. Esa URL se puede usar como referencia visual para Google Stitch.

### Servidor remoto + túnel juntos

```bash
npm run stitch
```

Levanta Flask en modo remoto y abre un túnel al puerto 5000 en paralelo.

## Flujo recomendado para Stitch

1. Instalar dependencias:

   ```bash
   python -m pip install -r requirements.txt
   npm install
   ```

2. Ejecutar:

   ```bash
   npm run stitch
   ```

3. Copiar la URL pública que imprime localtunnel.
4. Abrir esa URL en el navegador y navegar por las pantallas principales.
5. Usar esa URL o capturas de pantalla como referencia en Google Stitch.

## Datos locales de desarrollo

Los scripts npm usan:

```text
FINANZAS_DATA_DIR=.nexar-data
SECRET_KEY=nexar-dev-local-key
```

Esto evita mezclar pruebas de UI con una base local real del usuario. La carpeta `.nexar-data/` queda ignorada por Git.

## Seguridad

- No usar este modo con datos reales de clientes.
- No publicar la URL del túnel en lugares públicos.
- Cerrar el proceso cuando termine la revisión.
- El túnel es temporal y solo debe usarse para análisis visual/desarrollo.

## Nota técnica

Los scripts `dev:web` y `dev:remote` importan la instancia Flask desde `app.py`:

```bash
python -c "from app import app; app.run(...)"
```

De esta forma se evita ejecutar el bloque `if __name__ == '__main__'`, por lo que no se abre pywebview y la app queda disponible como servidor web simple.
