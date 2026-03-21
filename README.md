# 💰 Finanzas del Hogar v1.10.2

Aplicación de gestión financiera personal para escritorio. Funciona completamente
offline, utilizando base de datos SQLite local, y está optimizada para equipos
de gama media/baja.

**Creado por Rolando Navarta · Desarrollado junto a Claude.ai · 2026**

---

## 📦 Estructura del proyecto

```
finanzas_app/
├── app.py                → Punto de entrada Flask
├── models.py             → Schema de base de datos SQLite
├── routes.py             → Rutas y controladores HTTP
├── services.py           → Lógica de negocio y reportes
├── activation.py         → Validación de licencias (Token RSA + HMAC legacy)
├── demo_limits.py        → Control de tiers DEMO / BÁSICA / PRO
├── ai_service.py         → Módulo de inteligencia artificial
├── requirements.txt      → Dependencias Python
├── iniciar.bat           → Lanzador Windows
├── iniciar.sh            → Lanzador Linux/Mac
├── finanzas_hogar.ico    → Ícono de la aplicación (Windows)
├── finanzas_hogar.png    → Ícono de la aplicación (Linux)
├── database.db           → Base de datos (se crea al iniciar)
├── keys/
│   └── public_key.pem   → Clave pública RSA para verificación de licencias
├── licensing/            → Módulo de hardware ID y estado de licencia
└── templates/            → Plantillas HTML Jinja2
```

---

## 🚀 Instalación

### Requisitos
- Python 3.10 o superior
- pip

### Pasos

```bash
# 1. Ir a la carpeta del proyecto
cd finanzas_app/

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la aplicación
python app.py
```

### Inicio
La aplicación abre en una **ventana nativa** (pywebview). Si pywebview no está
disponible en el sistema, se abre automáticamente en el navegador predeterminado.

El puerto se asigna dinámicamente — si el 5000 está libre se usa ese, si no el
sistema elige uno disponible. El puerto real se muestra en la consola al iniciar.

En la primera ejecución se te pedirá crear tu usuario administrador.

### Windows — doble clic
Ejecutá `iniciar.bat`. Verifica Python, instala dependencias si hace falta y
abre la app automáticamente.

### Linux / Mac
```bash
chmod +x iniciar.sh
./iniciar.sh
```

> **Linux — ventana nativa:** para que pywebview funcione se necesitan las
> librerías GTK/WebKit:
> ```bash
> sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
> ```
> Si no están instaladas, la app abre en el navegador del sistema igualmente.

---

## 🔄 Actualizar una versión existente

> ⚠️ La instalación de actualizaciones está disponible solo en el **Plan Pro**.

Los datos, cuentas, historial y licencia **no se modifican** al actualizar.

1. Abrí la app → **Configuración** (barra lateral)
2. Sección **"Actualización del sistema"** al final de la página
3. Seleccioná el archivo `update_vX.X.X.zip`
4. Hacé clic en **"Instalar actualización"**
5. Reiniciá la aplicación

El sistema hace una copia de seguridad automática antes de aplicar cualquier
actualización.

---

## 🔐 Sistema de licencias

La aplicación usa un sistema de **3 planes** con activación por **Token Base64
firmado con RSA**, completamente offline.

### Planes disponibles

| Función | DEMO (30 días) | BÁSICA | PRO |
|---|:---:|:---:|:---:|
| Movimientos | Ilimitados | Ilimitados | Ilimitados |
| Cuentas | 3 en total | 1 por tipo | Ilimitadas |
| Inversiones | Hasta 3 | Solo lectura | Completo |
| Presupuestos | Ilimitados | Hasta 3 | Ilimitados |
| Reportes | Completos | Semanal + Mensual | Completos |
| IA (API key) | ✅ | ✅ | ✅ |
| Actualizaciones | ❌ | ❌ | ✅ |
| Soporte WhatsApp | ❌ | ❌ | ✅ |
| Duración | 30 días | Permanente | Mensual |
| Al vencer | Modo lectura | — | Vuelve a BÁSICA |

### DEMO
Los 30 días se cuentan desde la **primera ejecución**. Al vencer, podés seguir
viendo todos tus datos pero no agregar nuevos registros. El contador es
resistente a reinstalaciones — se guarda fuera de la base de datos.

### Activar un plan

1. Contactar al desarrollador para adquirir el token de activación
2. Ir a **Activar sistema** en el menú lateral
3. Pegar el token completo en el campo de activación
4. Hacer clic en **Activar plan**

El proceso es completamente offline. No requiere internet.

> Para activar el **Plan Pro** primero debe estar activo el **Plan Básico**.
> Si adquirís ambos, recibirás dos tokens — activar primero el Básico y luego el Pro.

### Solicitar licencia

La pantalla de activación muestra el **ID de tu equipo** con un botón para
enviarlo directamente por WhatsApp. El desarrollador usa ese ID para generar
tu token personalizado.

- 📱 WhatsApp: [+54 9 264 585-8874](https://wa.me/5492645858874)
- ✉️ rolojnb@outlook.com.ar

---

## 💾 Copias de seguridad

### Automáticas
Desde **Configuración → Copias de seguridad** podés programar backups automáticos:
- Frecuencias: diaria, semanal, mensual o nunca
- Retención configurable (3 a 20 copias)
- Se guardan en la carpeta `backups/` dentro de la aplicación
- Descarga directa desde el navegador

### Manual
```bash
# Windows
copy database.db backup_FECHA.db

# Linux/Mac
cp database.db backup_FECHA.db
```

Para restaurar: cerrá la app y reemplazá `database.db` con el backup.

---

## 📈 Inversiones — cotizaciones automáticas

| Tipo de activo | Fuente | Ejemplo ticker |
|---|---|---|
| Acciones argentinas | Yahoo Finance | `GGAL.BA`, `YPF.BA` |
| Acciones USA | Yahoo Finance | `AAPL`, `TSLA` |
| CEDEARs | Yahoo Finance | `TSLA.BA`, `AMZN.BA` |
| Bonos / Obligaciones | BYMA Open Data | `AL30`, `GD30` |
| FCI | API CAFCI (oficial) | Por nombre del fondo |
| Criptomonedas | CoinGecko | `BTC`, `ETH`, `SOL` |

Por cada posición muestra: costo promedio, valor a mercado, ganancia/pérdida y
rendimiento %. Disponible en Plan Pro; en Plan Básico es solo lectura.

---

## 💱 Cotizaciones en tiempo real

Sección **Cotizaciones** en el menú lateral:
- Todos los tipos de dólar (oficial, blue, MEP, CCL, cripto, mayorista, tarjeta)
- Monedas internacionales (EUR, BRL, CLP, UYU, GBP)
- Criptomonedas principales con variación 24hs

Fuentes: dolarapi.com · frankfurter.app · CoinGecko — todas gratuitas sin API key.
Los datos se cachean localmente para funcionar sin conexión.

---

## 📊 Funcionalidades completas

- ✅ Dashboard con resumen del mes y alertas
- ✅ Ingresos y gastos con categorías dinámicas e ilimitadas
- ✅ Múltiples cuentas (banco, billetera virtual, efectivo)
- ✅ Transferencias entre cuentas propias
- ✅ Presupuestos mensuales con semáforo de alertas
- ✅ Reportes mensual / anual / semanal con exportación CSV
- ✅ Inversiones con cotizaciones automáticas (Yahoo Finance, BYMA, CAFCI, CoinGecko)
- ✅ Cálculo de ganancias y pérdidas por posición
- ✅ Cotizaciones en tiempo real (dólar, monedas, cripto)
- ✅ Copias de seguridad automáticas programables
- ✅ Sistema de actualización sin pérdida de datos *(Plan Pro)*
- ✅ Clasificación de categorías: Necesario / Prescindible con análisis en Reportes
- ✅ Clasificación automática de gastos con IA
- ✅ Asistente financiero en lenguaje natural (chat flotante)
- ✅ Sistema de licencias por tiers: DEMO / BÁSICA / PRO
- ✅ Activación offline por Token RSA — sin internet
- ✅ Anti-reinstall: la demo no se reinicia borrando la base de datos
- ✅ Ventana nativa pywebview con fallback al navegador
- ✅ Puerto dinámico — sin conflictos de red
- ✅ Manual completo integrado

---

## 🤖 Inteligencia Artificial

La IA se configura en **Configuración → Inteligencia Artificial** ingresando
una clave de API de Anthropic. Disponible en todos los planes.

### Clasificación automática de gastos
Al ingresar una nueva transacción, la IA analiza la descripción en tiempo real
y sugiere la categoría más adecuada.

### Asistente financiero (chat flotante)
El ícono ✨ en la esquina inferior derecha abre un chat con acceso de lectura
a tus datos reales — transacciones, cuentas, presupuestos e inversiones.

> La clave de API se guarda localmente y nunca sale de tu equipo.
> Obtené tu clave en: https://console.anthropic.com/
> **Nota de costos:** la clave es gratuita pero cada consulta tiene un costo
> según el uso (Anthropic API).

---

## 🛠 Tecnologías utilizadas

- Python 3.10+ · Flask · SQLite · HTML5 + Jinja2
- pywebview (ventana nativa de escritorio)
- cryptography (verificación de licencias RSA)
- Yahoo Finance · BYMA · CAFCI · CoinGecko · dolarapi.com
- Anthropic API (IA opcional)

---

## 📋 Historial de versiones

| Versión | Cambios principales |
|---|---|
| **v1.10.2** | Fix crítico: sistema de actualización in-app escribe en el directorio correcto en instalaciones .deb |
| **v1.10.1** | Corrección: formulario de renovación Pro visible antes del vencimiento |
| **v1.10.0** | Sistema de licencias por tiers (DEMO/BÁSICA/PRO); activación por Token RSA; anti-reinstall; badge de plan; upgrade BÁSICA→PRO |
| **v1.9.2** | ID de máquina visible en pantalla de activación con botón copiar |
| **v1.9.1** | Licencia MIT visible en Acerca de como sección colapsable |
| **v1.9.0** | Corrección de cierre sin sesión activa; avisos de costo del asistente de IA |
| **v1.8.0** | Recuperación de contraseña por pregunta secreta |
| **v1.7.0** | Puerto dinámico — sin conflictos si el 5000 está ocupado |
| **v1.6.0** | Categorías Necesario/Prescindible; análisis con IA en Reportes; cierre de terminal |
| **v1.5.0** | Clasificación automática de gastos con IA; asistente financiero en chat |
| **v1.4.0** | Actualización sin pérdida de datos; instaladores .exe y .deb |
| **v1.3.0** | Corrección de categorías duplicadas; pantalla de licencia rediseñada |
| **v1.2.0** | Cotizaciones automáticas para inversiones; ganancias/pérdidas |
| **v1.1.0** | Cotizaciones en tiempo real; copias de seguridad automáticas |
| **v1.0.0** | Versión inicial |

---

*Creado por Rolando Navarta · Desarrollado junto a Claude.ai · 2026*
