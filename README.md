💰 Finanzas del Hogar v1.6.0


Aplicación web local de gestión financiera personal. Funciona offline, sin base de datos externa, y está optimizada para equipos de gama media/baja.

**Creado por Rolando Navarta · Desarrollado junto a Claude.ai · 2026**

---

## 📦 Estructura del proyecto

```
finanzas_app/
├── app.py                → Punto de entrada Flask
├── models.py             → Schema de base de datos SQLite
├── routes.py             → Rutas y controladores HTTP
├── services.py           → Lógica de negocio y reportes
├── activation.py         → Validación de códigos de licencia
├── demo_limits.py        → Control de límites DEMO
<<<<<<< HEAD
=======
├── ai_service.py         → Módulo de inteligencia artificial
>>>>>>> desarrollo
├── requirements.txt      → Dependencias Python
├── iniciar.bat           → Lanzador Windows
├── iniciar.sh            → Lanzador Linux/Mac
├── finanzas_hogar.ico    → Ícono de la aplicación (Windows)
├── finanzas_hogar.png    → Ícono de la aplicación (Linux)
├── database.db           → Base de datos (se crea al iniciar)
└── templates/
    ├── base.html               → Layout base con menú
    ├── login.html              → Pantalla de login
    ├── setup.html              → Configuración inicial
    ├── dashboard.html          → Panel principal
    ├── transactions.html       → Lista de movimientos
    ├── transaction_form.html
    ├── accounts.html           → Cuentas bancarias / billeteras
    ├── account_form.html
    ├── transfer_form.html      → Transferencias entre cuentas
    ├── categories.html         → Categorías dinámicas
    ├── budgets.html            → Presupuestos con semáforo
    ├── reports.html            → Reportes y gráficos
    ├── investments.html        → Inversiones con precios de mercado
    ├── investment_form.html    → Formulario con guía de tickers
    ├── cotizaciones.html       → Cotizaciones en tiempo real
    ├── activate.html           → Activación de licencia (visual)
    ├── settings.html           → Configuración + actualización del sistema
    ├── help.html               → Manual completo integrado
    ├── about.html              → Acerca de
    ├── shutdown.html           → Cierre del servidor
    └── error.html              → Página de error
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

# 2. Instalar dependencias (Flask es la única obligatoria)
pip install -r requirements.txt

# 3. Ejecutar la aplicación
python app.py
```

### Acceder
Abrí tu navegador en: **http://127.0.0.1:5000**

En la primera ejecución se te pedirá crear tu usuario administrador.

### Windows — doble clic
Ejecutá `iniciar.bat`. Verifica Python, instala Flask si hace falta y abre el navegador automáticamente.

### Linux / Mac
```bash
chmod +x iniciar.sh
./iniciar.sh
```

---

## 🔄 Actualizar una versión existente

Los datos, cuentas, historial y licencia **no se modifican** al actualizar.

1. Abrí la app → **Configuración** (barra lateral)
2. Sección **"Actualización del sistema"** al final de la página
3. Seleccioná el archivo `update_vX.X.X.zip`
4. Hacé clic en **"Instalar actualización"**
5. Reiniciá la aplicación

> ⚠️ El sistema hace una copia de seguridad automática antes de aplicar cualquier actualización.

---

## 🔐 Sistema de activación

### Versión DEMO (por defecto)
| Recurso | Límite |
|---|---|
| Gastos | 30 |
| Ingresos | 5 |
| Cuentas bancarias | 4 |
| Billeteras virtuales | 4 |
| Inversiones | 10 |

### Tipos de licencia
| Tipo | Descripción |
|---|---|
| **Mensual** | Válida un mes calendario, muestra fecha de vencimiento |
| **Permanente** | Sin fecha de vencimiento |
| **Cliente** | Licencia personalizada, sin vencimiento |

### Activar versión FULL
1. Obtener código de activación (contactar al desarrollador)
2. Ir a **Activar sistema** en el menú lateral
3. Ingresar el código (formato: `XXXX-XXXX-XXXX-XXXX`)
4. El sistema se activa offline, sin internet

### Contacto para licencias
- 📱 WhatsApp: +54 9 264 585-8874
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

El módulo de inversiones obtiene precios de mercado de forma automática desde fuentes gratuitas:

| Tipo de activo | Fuente | Ejemplo ticker |
|---|---|---|
| Acciones argentinas | Yahoo Finance | `GGAL.BA`, `YPF.BA` |
| Acciones USA | Yahoo Finance | `AAPL`, `TSLA` |
| CEDEARs | Yahoo Finance | `TSLA.BA`, `AMZN.BA` |
| Bonos / Obligaciones | BYMA Open Data | `AL30`, `GD30` |
| FCI | API CAFCI (oficial) | Por nombre del fondo |
| Criptomonedas | CoinGecko | `BTC`, `ETH`, `SOL` |

Por cada posición muestra: costo promedio, valor a mercado, ganancia/pérdida y rendimiento %.

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
- ✅ Ingresos y gastos con categorías dinámicas
- ✅ Múltiples cuentas (banco, billetera virtual, efectivo)
- ✅ Transferencias entre cuentas propias
- ✅ Presupuestos mensuales con semáforo de alertas
- ✅ Reportes mensual / anual / semanal
- ✅ Exportación CSV
- ✅ Inversiones con cotizaciones automáticas (Yahoo Finance, BYMA, CAFCI, CoinGecko)
- ✅ Cálculo de ganancias y pérdidas por posición
- ✅ Cotizaciones en tiempo real (dólar, monedas, cripto)
- ✅ Copias de seguridad automáticas programables
- ✅ Sistema de actualización sin pérdida de datos
- ✅ Licencia visual con tipo y fecha de vencimiento
<<<<<<< HEAD
=======
- ✅ **Clasificación de categorías: Necesario / Prescindible** con análisis y recomendaciones en Reportes
- ✅ **Cierre completo**: cierra terminal (Linux SIGHUP / Windows taskkill) y pestaña del navegador
- ✅ **Clasificación automática de gastos con IA** (sugiere categoría al escribir la descripción)
- ✅ **Asistente financiero en lenguaje natural** (chat flotante con acceso a todos tus datos)
>>>>>>> desarrollo
- ✅ Sistema DEMO / FULL con activación offline
- ✅ Manual completo integrado
- ✅ Cierre controlado del servidor

---

<<<<<<< HEAD
=======
## 🤖 Inteligencia Artificial

La IA se configura en **Configuración → Inteligencia Artificial** ingresando una clave de API de Anthropic.

### Clasificación automática de gastos
Al ingresar una nueva transacción, la IA analiza la descripción en tiempo real y sugiere la categoría más adecuada. El usuario puede aceptar o ignorar la sugerencia. Si no hay clave configurada, el campo funciona normalmente sin IA.

### Asistente financiero (chat flotante)
El ícono ✨ en la esquina inferior derecha abre un chat que responde preguntas en lenguaje natural sobre las finanzas del usuario:
- *¿Cómo cerré el mes?*
- *¿En qué gasté más?*
- *¿Cómo van mis presupuestos?*
- *¿Cuánto ahorré este mes?*

El asistente tiene acceso de solo lectura a los datos reales del usuario (transacciones, cuentas, presupuestos, inversiones). Requiere conexión a internet.

> La clave de API se guarda localmente en la base de datos del usuario y nunca se envía a servidores propios.
> Obtené tu clave en: https://console.anthropic.com/

---
>>>>>>> desarrollo
## 📋 Historial de versiones

| Versión | Cambios principales |
|---|---|
<<<<<<< HEAD
=======
| **v1.6.0** | Categorías Necesario/Prescindible; análisis con recomendaciones y IA en Reportes; cierre de terminal y pestaña al apagar |
| **v1.5.0** | Clasificación automática de gastos con IA (sugiere categoría al escribir); asistente financiero en chat flotante con acceso a datos reales del usuario |
>>>>>>> desarrollo
| **v1.4.1** | Corrección: sección de actualización duplicada en Configuración; corrección: error "falta UPDATE_META.json" al instalar actualizaciones |
| **v1.4.0** | Sistema de actualización sin pérdida de datos desde Configuración; instaladores Windows (.exe x64/x86) y Linux (.deb); versión portable mejorada |
| **v1.3.0** | Corrección de categorías duplicadas en DB; pantalla de licencia rediseñada con tipo y fecha de vencimiento visual |
| **v1.2.0** | Cotizaciones de mercado automáticas para inversiones; cálculo de ganancias/pérdidas; campo ticker con guía contextual |
| **v1.1.0** | Cotizaciones en tiempo real (dólar, forex, cripto); copias de seguridad automáticas programables; botón de cierre en login |
| **v1.0.0** | Versión inicial |

---

*Creado por Rolando Navarta · Desarrollado junto a Claude.ai · 2026*
