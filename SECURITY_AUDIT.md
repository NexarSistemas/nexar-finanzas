# 🔒 Auditoría de Seguridad — Nexar Finanzas

**Fecha:** 30 de marzo de 2026  
**Versión:** v1.10.1  
**Estado:** ⚠️ Se detectaron vulnerabilidades críticas y moderadas

---

## 📋 Resumen Ejecutivo

Se han identificado **7 vulnerabilidades** con severidad crítica a moderada que requieren atención inmediata:

| Severidad | Cantidad | Estado |
|-----------|----------|--------|
| 🔴 Crítica | 2 | Requiere acción inmediata |
| 🟠 Alta | 3 | Requiere acción pronta |
| 🟡 Moderada | 2 | Debe corregirse |

---

## 🔴 VULNERABILIDADES CRÍTICAS

### 1. **Clave HMAC hardcodeada en el código fuente** (CRÍTICA)
**Ubicación:** [activation.py](activation.py#L165)  
**Severidad:** 🔴 CRÍTICA  
**CVSS:** 9.8

```python
_SECRET_KEY = b"NexarFinanzas2026_RolandoNavarta_SecretKey_X9Z"
```

**Problema:**
- La clave secreta para validación de licencias HMAC está expuesta en el código fuente
- Cualquiera con acceso al repositorio o archivo compilado puede generar licencias falsas
- Sistema legacy pero aún funcional para compatibilidad

**Impacto:**
- Generación de licencias fraudulentas
- Bypass del sistema de activación
- Pérdida de ingresos por piratería

**Recomendación:**
- ❌ **NO** almacenar claves secretas en código fuente
- ✅ Usar variables de entorno cifradas (`.env` local no versionado)
- ✅ Deshabilitar completamente el sistema HMAC legacy
- ✅ Migrar clientes al sistema RSA

---

### 2. **SECRET_KEY de Flask con valor por defecto débil** (CRÍTICA)
**Ubicación:** [app.py](app.py#L209)  
**Severidad:** 🔴 CRÍTICA  
**CVSS:** 9.1

```python
app.secret_key = os.environ.get(
    'FLASK_SECRET_KEY',
    'NexarFinanzas_2026_SessionKey_Change_In_Prod_XK9Z'
)
```

**Problema:**
- El valor por defecto es predecible y público (visible en código fuente)
- Si no se configura la variable de entorno, se usa esta clave débil
- La clave es la misma para todas las instalaciones por defecto

**Impacto:**
- Falsificación de cookies de sesión (session hijacking)
- Un atacante puede logearse como cualquier usuario sin contraseña
- Pérdida total de confidencialidad de datos

**Recomendación:**
```python
# Generar automáticamente una clave segura al primer inicio
import secrets

secret_key = os.environ.get('FLASK_SECRET_KEY')
if not secret_key:
    if not _user_exists():
        # Primera ejecución: generar y guardar clave segura
        secret_key = secrets.token_hex(32)
        # Guardar en archivo protegido (no versionado)
    else:
        # Error: requiere FLASK_SECRET_KEY
        raise RuntimeError("FLASK_SECRET_KEY no configurada")

app.secret_key = secret_key
```

---

## 🟠 VULNERABILIDADES ALTAS

### 3. **Contraseña con longitud mínima muy baja (4 caracteres)** (ALTA)
**Ubicación:** [routes.py](routes.py#L109), [templates/setup.html](templates/setup.html#L23)  
**Severidad:** 🟠 ALTA  
**Impact:** Fácil ataque de fuerza bruta

**Problema:**
- Mínimo de 4 caracteres es insuficiente (65,536 combinaciones alfanuméricas)
- No hay complejidad obligatoria (mayúsculas, números, símbolos)
- No hay límite de intentos de login fallidos

**Recomendación:**
```python
# Aumentar a 12 caracteres mínimo
if len(password) < 12:
    flash('La contraseña debe tener al menos 12 caracteres.', 'danger')

# Implementar rate limiting en login
# Bloquear después de 5 intentos fallidos por 15 minutos
```

---

### 4. **Ausencia de protección CSRF (Cross-Site Request Forgery)** (ALTA)
**Ubicación:** Toda la aplicación  
**Severidad:** 🟠 ALTA  

**Problema:**
- No hay validación de tokens CSRF en formularios POST
- Un sitio malicioso puede realizar acciones en nombre del usuario
- Especialmente crítico en cambios de contraseña y configuración

**Recomendación:**
```python
# Instalar Flask-WTF
pip install Flask-WTF

# En app.py
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# En templates
<form method="POST">
    {{ csrf_token() }}
</form>
```

---

### 5. **Clave API de Anthropic almacenada en texto plano en base de datos** (ALTA)
**Ubicación:** [routes.py](routes.py#L1025), [models.py](models.py#L361)  
**Severidad:** 🟠 ALTA  

**Problema:**
- La clave de API se guarda sin cifrado en SQLite
- Cualquiera con acceso al archivo `.db` obtiene credenciales de terceros
- Si la BD se sincroniza a la nube, expone la clave

**Recomendación:**
```python
# Crear módulo de cifrado para datos sensibles
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self, master_password):
        self.cipher = Fernet(derive_key_from_password(master_password))
    
    def encrypt_value(self, value):
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt_value(self, encrypted):
        return self.cipher.decrypt(encrypted.encode()).decode()

# Más seguro: usar variables de entorno
# api_key = os.environ.get('ANTHROPIC_API_KEY')
```

---

## 🟡 VULNERABILIDADES MODERADAS

### 6. **Sin protección contra ataque de fuerza bruta en recuperación de contraseña** (MODERADA)
**Ubicación:** [routes.py](routes.py#L152)  
**Severidad:** 🟡 MODERADA  

**Problema:**
- No hay límite de intentos para adivinar la respuesta de seguridad
- Un atacante puede probar miles de respuestas sin restricción
- La respuesta se normaliza a minúsculas pero eso no es suficiente

**Recomendación:**
```python
# Implementar contador de intentos fallidos
# Después de 3 intentos fallidos, esperar 5 minutos
# Guardar timestamp del último intento en sesión

if 'recovery_attempts' not in session:
    session['recovery_attempts'] = 0
    session['recovery_locked_until'] = None

if session.get('recovery_locked_until'):
    if datetime.now() < session['recovery_locked_until']:
        flash('Muchos intentos fallidos. Intenta más tarde.', 'danger')
        return redirect(url_for('login'))

# Incrementar contador...
```

---

### 7. **Validación insuficiente de descargas de licencias desde Google Drive** (MODERADA)
**Ubicación:** [licensing/license_api.py](licensing/license_api.py#L60)  
**Severidad:** 🟡 MODERADA  

**Problema:**
- Solo verifica código HTTP 200, no valida integridad del contenido
- No hay verificación de firma criptográfica (crypto_verify.py está vacío)
- MITM (Man-in-the-Middle) puede interceptar la respuesta

**Recomendación:**
```python
# Implementar verificación de firma RSA
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

def verify_license_signature(license_json, signature_b64, public_key):
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            json.dumps(license_json).encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False

# En license_api.py
license_json = r.json()
if not verify_license_signature(license_json, license_json['signature'], PUBLIC_KEY):
    raise RuntimeError("Firma de licencia inválida")
```

---

## 🟢 PRÁCTICAS SEGURAS DETECTADAS

✅ **Uso correcto de prepared statements**
- Todas las consultas SQL usan placeholders (`?`) para prevenir SQL injection
- Buen ejemplo en [routes.py](routes.py#L87)

✅ **Hashing de contraseñas con SHA-256**
- Las contraseñas se hashean, no se almacenan en texto plano
- Se aplica a ambas contraseñas de usuario y respuestas de seguridad

✅ **Validación básica de entrada**
- Límites de longitud en formularios
- Validación de tipos de datos (numbers, dates)

✅ **Autenticación requerida en rutas**
- Decorador `@login_required` en rutas protegidas
- Redirección correcta al login si no hay sesión

---

## ⚠️ PROBLEMAS MENORES

### 8. **No hay HTTPS/TLS configurado**
- La aplicación corre en HTTP local (pywebview)
- Si alguna vez se expone a red, es vulnerable al tráfico en claro

### 9. **Falta header de seguridad: Content-Security-Policy**
- No hay protección contra XSS via scripts inline

### 10. **No hay logging de eventos de seguridad**
- No se registran intentos de login fallidos
- No hay auditoría de cambios de configuración sensible

---

## 🎯 PLAN DE ACCIÓN PRIORITARIO

### Hacer AHORA (Crítico):
- [ ] **Deshabilitar sistema HMAC**
  - Eliminar `_SECRET_KEY` de `activation.py`
  - Usar `activar_token_rsa()` exclusivamente
  
- [ ] **Generar SECRET_KEY al primer inicio**
  - Reemplazar valor por defecto con generación segura
  - Guardar en archivo de configuración no versionado

### Próxima semana:
- [ ] Implementar CSRF protection con Flask-WTF
- [ ] Aumentar requisito de contraseña a 12+ caracteres
- [ ] Añadir rate limiting en login y recuperación

### Este mes:
- [ ] Cifrar API keys en la base de datos
- [ ] Implementar verificación de firma en licencias RSA
- [ ] Agregar logging de eventos de seguridad
- [ ] Implementar HTTPS/TLS local

---

## 📚 Referencias de Seguridad

- [OWASP Top 10 2023](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)
- [CWE-327: Use of Broken/Risky Cryptographic Algorithm](https://cwe.mitre.org/data/definitions/327.html)
- [CWE-256: Plaintext Storage of Password](https://cwe.mitre.org/data/definitions/256.html)

---

**Auditoría realizada por:** GitHub Copilot  
**Próxima revisión:** Después de implementar correcciones críticas
