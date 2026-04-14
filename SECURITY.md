# Security Policy

## 📌 Versiones soportadas

Este proyecto se encuentra en desarrollo activo.

| Versión | Soporte |
|--------|--------|
| 1.10.x | ✅ Soporte activo |
| < 1.10.0 | ❌ No soportado |

---

## 🚨 Reporte de vulnerabilidades

Si encontrás una vulnerabilidad de seguridad, por favor **NO abrir un issue público**.

Contactar por:

- 📧 Email: nexarsistemas@outlook.com.ar  
- 📱 WhatsApp: +54 9 264 585-8874  

### 📋 Información requerida

- Descripción del problema  
- Pasos para reproducirlo  
- Impacto potencial (ej: acceso a datos financieros)  
- Evidencia (logs, capturas, etc.)  

---

## ⏱️ Tiempos de respuesta

- Confirmación: dentro de 48 horas  
- Evaluación: 3 a 5 días  
- Resolución: según criticidad  

---

## 🔒 Alcance del sistema

Nexar Finanzas es una aplicación de gestión financiera personal que incluye:

- Gestión de ingresos y gastos  
- Cuentas y transferencias  
- Presupuestos  
- Inversiones  
- Sistema de licencias offline  
- Integración opcional con IA (API externa)  

---

## 🔍 Áreas críticas

### 💰 Datos financieros
- Transacciones (ingresos/gastos)  
- Cuentas y saldos  
- Inversiones  
- Historial financiero completo  

⚠️ Estos datos son altamente sensibles.

---

### 🔐 Autenticación
- Usuario administrador  
- Recuperación de contraseña  
- Manejo de sesiones  

---

### 🔑 Configuración sensible

- `SECRET_KEY` (obligatoria desde v1.10.5)  
- Variables de entorno (`.env`)  
- API Key de IA (Anthropic)  

⚠️ La API Key se almacena localmente y es responsabilidad del usuario.

---

### 🤖 Integración con IA

- Uso de API externa (Anthropic)  
- Envío de datos para análisis  

⚠️ El usuario debe ser consciente del posible costo y exposición de datos.

---

### 🧾 Sistema de licencias

- Tokens Base64 firmados con RSA  
- Anti-reinstall (`telemetry.bin`)  
- Hardware ID  

---

### 💾 Base de datos

- Archivo `database.db`  
- Contiene toda la información financiera  

⚠️ El acceso al archivo implica acceso total a los datos.

---

### 📦 Backups

- Carpeta `backups/`  
- Copias automáticas descargables  

⚠️ Pueden contener información sensible completa.

---

## ⚠️ Buenas prácticas implementadas

- Eliminación de `SECRET_KEY` hardcodeada (v1.10.5)  
- Uso de variables de entorno para configuración crítica  
- Validación de datos de entrada  
- Protección CSRF en formularios  
- Hash de contraseñas y respuestas de seguridad  
- Firma digital de releases (GPG + SHA256)  
- Pipeline CI/CD con validaciones de seguridad  

---

## 🚫 Prácticas consideradas vulnerabilidades

Se consideran fallos críticos:

- Hardcodear `SECRET_KEY` o claves sensibles  
- Subir `.env` al repositorio  
- Exponer API keys (IA)  
- Manipular `database.db` directamente  
- Acceso sin autenticación a endpoints  
- Exposición de backups  
- Bypass del sistema de licencias  
- Interceptar o modificar datos enviados a APIs externas  

---

## 🧪 Entornos

El sistema está diseñado para:

- Ejecución local (offline-first)  
- Uso personal en equipos individuales  

⚠️ No está diseñado para exposición directa a internet sin medidas adicionales.

---

## 📦 Dependencias

Se utilizan herramientas automáticas:

- Dependabot alerts  
- Dependabot security updates  

Se recomienda mantener las dependencias actualizadas.

---

## 🆕 Cambios relevantes de seguridad

### v1.10.8
- Actualización de dependencias de seguridad  

### v1.10.5
- Eliminación de `SECRET_KEY` hardcodeada  
- Uso obligatorio de variables de entorno  
- Corrección de errores CSRF  

### v1.10.3
- Firma digital GPG de releases  
- Generación de hashes SHA256  

### v1.10.0
- Sistema de licencias RSA  
- Anti-reinstall  
- Validación de hardware ID  

---

## 🙏 Reconocimiento

Se agradece a quienes reporten vulnerabilidades de forma responsable.

---

## 📢 Nota final

Este software maneja información financiera personal sensible.  
La seguridad depende tanto del sistema como del uso responsable por parte del usuario, especialmente en el manejo de backups, claves y acceso al equipo.
