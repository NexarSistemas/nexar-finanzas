# 💰 Nexar Finanzas v1.13.1

Aplicación de gestión financiera personal para escritorio. Funciona completamente
offline, utilizando base de datos SQLite local, y está optimizada para equipos
de gama media/baja.

Estado actual:

- Estado del repositorio: activo
- Version actual: `1.13.1`
- Contexto central del ecosistema: repo externo `nexar-ai-context`, archivo `CONTEXTO_NEXAR.md`

> Nota: los estándares de seguridad compartidos de Nexar se mantienen en `nexar-ai-context/standards/`.
**Desarrollado por Nexar Sistemas - (c) 2026**

---

## 📦 Estructura del proyecto

```
finanzas_app/
├── app.py                → Punto de entrada Flask
├── models.py             → Schema de base de datos SQLite
├── routes.py             → Rutas y controladores HTTP
├── services.py           → Lógica de negocio y reportes
├── demo_limits.py        → Control de tiers DEMO / BASICA / PRO / FULL
├── ai_service.py         → Módulo de inteligencia artificial
├── requirements.txt      → Dependencias Python para desarrollo/ejecución local
├── requirements-build.txt → Dependencias de empaquetado PyInstaller
├── iniciar.bat           → Lanzador Windows
├── iniciar.sh            → Lanzador Linux/Mac
├── nexar_finanzas.ico    → Ícono de la aplicación (Windows)
├── nexar_finanzas.png    → Ícono de la aplicación (Linux)
├── database.db           → Base de datos (se crea al iniciar)
├── keys/
│   └── public_key.pem   → Clave pública opcional para el SDK
├── licensing/            → SDK, Supabase, hardware ID y estado de licencia
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

`requirements.txt` no requiere acceso al repositorio privado del SDK de
licencias. Los builds oficiales usan `requirements-build.txt`, que agrega
`nexar_licencias` fijado a una release concreta para empaquetarlo dentro de los
instaladores.

### Windows — doble clic

Ejecutá `iniciar.bat`. Verifica Python, instala dependencias si hace falta y
abre la app automáticamente.

### Linux / Mac

```bash
chmod +x iniciar.sh
./iniciar.sh
```

> **Linux — ventana nativa:** los builds oficiales usan Qt/PySide6 empaquetado
> dentro de la aplicación. Si la ventana nativa falla, la app abre en el
> navegador del sistema igualmente.

## Builds y publicación

El workflow **Build & Release Nexar Finanzas** compila Linux, Windows y macOS.
Para generar builds de prueba, abrí **Actions**, elegí el workflow y usá **Run
workflow**. La ejecución manual no crea tags ni Releases. Los resultados se
descargan desde la sección **Artifacts** de la ejecución y se conservan 14 días:

- `nexar-finanzas-linux-X.Y.Z`: `.deb` y portable `.tar.gz`.
- `nexar-finanzas-windows-X.Y.Z`: instalador `.exe` y portable `.zip`.
- `nexar-finanzas-macos-X.Y.Z`: aplicación `.app`, `.zip` y `.dmg`.
- `nexar-finanzas-final-X.Y.Z`: paquetes de las tres plataformas, hashes SHA256
  y firmas `.sig` cuando están configurados los secretos GPG.

Los pull requests internos y los pushes a `main` también generan Artifacts, pero
nunca publican una Release. En PR provenientes de forks se ejecuta la validación
de versión y changelog, mientras que los builds se omiten de forma segura porque
GitHub no entrega los secretos ni la Deploy Key requeridos por el SDK privado.

Una Release oficial se publica únicamente al hacer push de un tag SemVer. Antes,
`VERSION` debe contener `X.Y.Z` y `CHANGELOG.md` debe incluir `## [X.Y.Z]`; ambos
cambios deben estar mergeados en `main`. El tag debe coincidir exactamente:

```bash
git checkout main
git pull origin main

# Verificar VERSION y CHANGELOG.md

git tag -a vX.Y.Z -m "Nexar Finanzas vX.Y.Z"
git push origin vX.Y.Z
```

El build de macOS se genera inicialmente sin firma ni notarización. La aplicación
es utilizable, pero Gatekeeper puede mostrar una advertencia. Firmar y notarizar
requiere certificados válidos y una cuenta Apple Developer; su ausencia no
impide generar los Artifacts de prueba.

La actualización automática dentro de la aplicación sigue disponible en Linux
y Windows. En macOS está desactivada temporalmente: la app puede informar que
existe una versión nueva, pero el usuario debe descargar e instalar manualmente
el `.dmg` o `.zip` desde la Release.

---

## 🔄 Actualizar una versión existente

> ⚠️ La instalación de actualizaciones está disponible solo en los planes **PRO** y **FULL**.

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

La aplicación usa el sistema unificado de licencias de Nexar, igual que
Nexar Tienda y Nexar Almacén: solicitud manual, aprobación en Nexar Admin,
clave de licencia y validación con Supabase + SDK `nexar_licencias`.

### Planes disponibles

| Función | DEMO (30 días) | BASICA | PRO | FULL |
|---|:---:|:---:|:---:|:---:|
| Movimientos | Ilimitados | Ilimitados | Ilimitados | Ilimitados |
| Cuentas | 3 en total | 1 por tipo | Ilimitadas | Ilimitadas |
| Inversiones | Hasta 3 | Solo lectura | Completo | Completo |
| Presupuestos | Ilimitados | Hasta 3 | Ilimitados | Ilimitados |
| Reportes semanales y mensuales | ✅ | ✅ | ✅ | ✅ |
| Reportes avanzados | ✅ | ❌ | ❌ | ✅ |
| Análisis de flujo de caja | ✅ | ❌ | ✅ | ✅ |
| IA integrada (API key) | ✅ | ✅ | ✅ | ✅ |
| Insights financieros IA | ❌ | ❌ | ❌ | ✅ |
| Exportar Excel/PDF | ❌ | ❌ | ✅ | ✅ |
| Actualizaciones | ❌ | ❌ | ✅ | ✅ |
| Soporte WhatsApp | ❌ | ❌ | ✅ | ✅ |
| Duración | 30 días | Permanente | Mensual | Mensual |
| Al vencer | Modo lectura | — | BASICA o DEMO_EXPIRED | BASICA o DEMO_EXPIRED |

### DEMO

Los 30 días se cuentan desde la **primera ejecución**. Al vencer, podés seguir
viendo todos tus datos pero no agregar nuevos registros. El contador es
resistente a reinstalaciones — se guarda fuera de la base de datos.

### Activar un plan

1. Contactar al desarrollador o enviar una solicitud desde **Activar sistema**
2. Ir a **Activar sistema** en el menú lateral
3. Pegar la clave de licencia aprobada
4. Hacer clic en **Activar plan**

La activación inicial requiere conexión para validar la clave y vincular el
equipo. Después queda cache local para continuidad offline.

Flujos válidos de activación:

- DEMO → BASICA
- DEMO → PRO
- DEMO → FULL
- BASICA → PRO
- BASICA → FULL

Ya no se exige **BASICA previa** para activar un plan mensual. Si activás una
licencia **PRO** o **FULL** sobre una instalación limpia, queda habilitada sin
pasos intermedios.

Cuando vence un plan **PRO** o **FULL**:

- vuelve a **BASICA** si el usuario ya tenía **BASICA** activada
- pasa a **DEMO_EXPIRED** si nunca tuvo **BASICA**

### Solicitar licencia

La pantalla de activación muestra el **ID de activación** específico de
Nexar Finanzas y permite enviar una solicitud a Supabase. El desarrollador la
aprueba desde Nexar Admin y emite la clave de licencia.

- 📱 WhatsApp: [+54 9 264 585-8874](https://wa.me/5492645858874)
- ✉️ <nexarsistemas@outlook.com.ar>

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
rendimiento %. Disponible en **PRO** y **FULL**; en **BASICA** es solo lectura.

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
- ✅ Cuentas bancarias con descubierto autorizado y límite configurable
- ✅ Transferencias entre cuentas propias
- ✅ Presupuestos mensuales con semáforo de alertas
- ✅ Reportes mensual / anual / semanal con exportación CSV y exportación Excel/PDF para planes PRO y FULL
- ✅ Reportes básicos de liquidez con saldo neto, fondos positivos, descubierto usado y margen disponible
- ✅ Inversiones con cotizaciones automáticas (Yahoo Finance, BYMA, CAFCI, CoinGecko)
- ✅ Cálculo de ganancias y pérdidas por posición
- ✅ Cotizaciones en tiempo real (dólar, monedas, cripto)
- ✅ Copias de seguridad automáticas programables
- ✅ Sistema de actualización sin pérdida de datos *(Planes PRO y FULL)*
- ✅ Clasificación de categorías: Necesario / Prescindible con análisis en Reportes
- ✅ Clasificación automática de gastos con IA
- ✅ Asistente financiero en lenguaje natural (chat flotante)
- ✅ Sistema de licencias por tiers: DEMO / BASICA / PRO / FULL
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
> Obtené tu clave en: <https://console.anthropic.com/>
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
| **v1.12.0** | Salud Financiera Fase 1 y Reportes completos con ahorro, balance y tasa de ahorro |
| **v1.11.0** | Bloque funcional de descubierto bancario: soporte, UX visual y reportes básicos |
| **v1.10.16** | Inicio sin aviso previo de demo/activacion y ventana nativa maximizada |
| **v1.10.8** | security: actualizar dependencias y unificar requerimientos |
| **v1.10.7** | Actualización de versión. |
| **v1.10.6** | Avisos de vencimiento para el Plan Pro (5 días y 1 día antes) |
| **v1.10.5** | Integración de SECRET_KEY mediante variables de entorno (.env y GitHub Secrets) |
| **v1.10.4** | Pipeline de releases estabilizado y mejoras en CI/CD |
| **v1.10.3** | Pipeline de build automatizado; firma digital GPG; release automática basada en CHANGELOG |
| **v1.10.2** | Fix crítico: sistema de actualización in-app escribe en el directorio correcto en instalaciones .deb |
| **v1.10.1** | Corrección: formulario de renovación Pro visible antes del vencimiento |
| **v1.10.0** | Sistema de licencias por tiers (DEMO/BÁSICA/PRO); anti-reinstall; badge de plan; upgrade BÁSICA→PRO |
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

*Desarrollado por Nexar Sistemas - &copy; 2026*
