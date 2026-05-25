"""
models.py
Inicialización y esquema de la base de datos SQLite.
Crea todas las tablas necesarias si no existen.
"""

import json
import sqlite3
import platform
import uuid
from datetime import date
import base64 as _b64
import hashlib as _hl


# ─── Anti-reinstall — archivo externo de control de demo ─────────────────────
#
# Guarda la fecha de inicio de demo en un archivo FUERA de la BD.
# Si el usuario borra la BD, el archivo sobrevive y mantiene la fecha original.
# Nombre y contenido diseñados para no llamar la atención.
# Carpeta: %APPDATA%\NexarFinanzas\  (Windows)
#          ~/.local/share/NexarFinanzas/  (Linux/Mac)
# Archivo: telemetry.bin
#

def _get_telemetry_path() -> str:
    """Ruta del archivo externo de control de demo."""
    if platform.system() == 'Windows':
        import os
        base   = os.environ.get('APPDATA', os.path.expanduser('~'))
        folder = os.path.join(base, 'NexarFinanzas')
    else:
        import os
        base   = os.environ.get('XDG_DATA_HOME',
                                os.path.join(os.path.expanduser('~'), '.local', 'share'))
        folder = os.path.join(base, 'NexarFinanzas')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, 'telemetry.bin')


def _encode_date(date_str: str, machine_id: str) -> str:
    """
    Codifica la fecha junto con el machine_id para que el contenido
    no sea legible ni obvio.
    Formato interno: base64( sha256(machine_id)[:8] + ":" + date_str )
    """
    salt = _hl.sha256(machine_id.encode()).hexdigest()[:8]
    raw  = f"{salt}:{date_str}"
    return _b64.b64encode(raw.encode()).decode()


def _decode_date(encoded: str, machine_id: str) -> str | None:
    """
    Decodifica y verifica que el contenido corresponda a este machine_id.
    Retorna la fecha ISO o None si es inválido o de otra máquina.
    """
    try:
        raw  = _b64.b64decode(encoded.strip()).decode()
        salt = _hl.sha256(machine_id.encode()).hexdigest()[:8]
        if not raw.startswith(f"{salt}:"):
            return None  # archivo de otra máquina o corrupto
        return raw.split(":", 1)[1]
    except Exception:
        return None


def _read_telemetry(machine_id: str) -> str | None:
    """
    Lee la fecha de instalación del archivo externo.
    Retorna fecha ISO string o None si no existe o es inválido.
    """
    path = _get_telemetry_path()
    try:
        with open(path, 'r') as f:
            encoded = f.read().strip()
        return _decode_date(encoded, machine_id)
    except Exception:
        return None


def _write_telemetry(date_str: str, machine_id: str) -> bool:
    """
    Escribe la fecha de instalación en el archivo externo.
    Retorna True si tuvo éxito.
    """
    path = _get_telemetry_path()
    try:
        encoded = _encode_date(date_str, machine_id)
        with open(path, 'w') as f:
            f.write(encoded)
        return True
    except Exception:
        return False


def _generate_machine_id() -> str:
    """
    Genera el hardware ID de esta PC usando la misma lógica
    que licensing/hardware_id.py para garantizar consistencia.
    """
    raw = (
        platform.node()
        + platform.system()
        + platform.machine()
        + str(uuid.getnode())
    )
    return _hl.sha256(raw.encode()).hexdigest()


def get_db(db_path: str) -> sqlite3.Connection:
    """Abre conexión a la base de datos con Row Factory para acceso por nombre."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Mejor rendimiento
    return conn


def get_config(db_path: str) -> dict:
    """Devuelve la tabla config como diccionario."""
    conn = get_db(db_path)
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def set_config(db_path: str, values: dict) -> None:
    """Inserta o actualiza claves de configuracion."""
    conn = get_db(db_path)
    for key, value in values.items():
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, "" if value is None else str(value)),
        )
    conn.commit()
    conn.close()


def normalize_license_plan(plan: str | None) -> str:
    raw = (plan or "BASICA").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BASIC": "BASICA",
        "BASICO": "BASICA",
        "BASICA": "BASICA",
        "DEMO": "DEMO",
        "PRO": "PRO",
        "MENSUAL_PRO": "PRO",
        "FULL": "FULL",
        "MENSUAL": "FULL",
        "MENSUAL_FULL": "FULL",
    }
    return aliases.get(raw, "BASICA")


def _local_tier_from_plan(plan: str | None) -> str:
    return normalize_license_plan(plan)


def sync_license_from_remote(db_path: str, license_data: dict) -> None:
    """Guarda en SQLite la licencia normalizada que devuelve Supabase/SDK."""
    data = dict(license_data or {})
    plan = normalize_license_plan(data.get("plan") or data.get("tier") or data.get("license_plan"))
    tier = _local_tier_from_plan(plan)
    expires_at = data.get("expira") or data.get("expires_at") or ""
    license_key = data.get("license_key") or ""
    max_devices = data.get("max_devices") or data.get("max_machines") or 1

    cfg = get_config(db_path)
    basica_activada = cfg.get("basica_activada", "0") == "1" or tier == "BASICA"

    values = {
        "version": "DEMO" if tier == "DEMO" else "FULL",
        "license_tier": tier,
        "license_plan": plan,
        "license_expires_at": "" if tier == "BASICA" else expires_at,
        "license_key": license_key,
        "license_signature": data.get("public_signature") or data.get("signature") or "",
        "license_type": "supabase",
        "license_activated_at": data.get("activated_at") or data.get("created_at") or date.today().isoformat(),
        "license_last_check": date.today().isoformat(),
        "license_max_devices": max_devices,
        "license_data_full": json.dumps(data, ensure_ascii=False, sort_keys=True),
        "basica_activada": "1" if basica_activada else "0",
    }
    set_config(db_path, values)


def init_db(db_path: str):
    """Crea todas las tablas si no existen e inserta datos iniciales."""
    conn = get_db(db_path)
    cur = conn.cursor()

    # Configuración general del sistema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Usuario único del sistema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id                    INTEGER PRIMARY KEY CHECK (id = 1),
            username              TEXT NOT NULL DEFAULT 'admin',
            password_hash         TEXT NOT NULL,
            recovery_question     TEXT,
            recovery_answer_hash  TEXT,
            created_at            TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Migración segura: agregar campos de recuperación si no existen ──────
    cols_user = [row[1] for row in cur.execute("PRAGMA table_info(user)").fetchall()]
    if 'recovery_question' not in cols_user:
        cur.execute("ALTER TABLE user ADD COLUMN recovery_question TEXT")
    if 'recovery_answer_hash' not in cols_user:
        cur.execute("ALTER TABLE user ADD COLUMN recovery_answer_hash TEXT")

    # Cuentas: bancarias, billeteras virtuales, efectivo
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL CHECK (type IN ('bank','virtual_wallet','cash')),
            currency        TEXT NOT NULL DEFAULT 'ARS' CHECK (currency IN ('ARS','USD')),
            initial_balance REAL NOT NULL DEFAULT 0,
            current_balance REAL NOT NULL DEFAULT 0,
            cbu_cvu         TEXT,
            alias           TEXT,
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Categorías dinámicas para ingresos y gastos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT NOT NULL,
            type   TEXT NOT NULL CHECK (type IN ('income','expense')),
            active       INTEGER NOT NULL DEFAULT 1,
            es_necesario INTEGER NOT NULL DEFAULT 1,  -- 1=necesario, 0=prescindible
            UNIQUE(name, type)
        )
    """)

    # ── Migración segura: agregar es_necesario si la columna no existe ──────────
    cols_cats = [row[1] for row in cur.execute("PRAGMA table_info(categories)").fetchall()]
    if 'es_necesario' not in cols_cats:
        cur.execute("ALTER TABLE categories ADD COLUMN es_necesario INTEGER NOT NULL DEFAULT 1")
        # Marcar como prescindibles las categorías que claramente no son necesidades básicas
        prescindibles = ('Entretenimiento','Ocio','Salidas','Restaurantes','Viajes',
                         'Ropa','Suscripciones','Regalos','Hobbies','Juegos',
                         'Vacaciones','Lujo','Deportes','Streaming')
        for nombre in prescindibles:
            cur.execute("UPDATE categories SET es_necesario=0 WHERE name=? AND type='expense'", (nombre,))
        conn.commit()

    # Cuentas por cobrar / pagar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receivables_payables (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            type          TEXT NOT NULL CHECK (type IN ('receivable','payable')),
            description   TEXT NOT NULL,
            person        TEXT,
            amount        REAL NOT NULL,
            due_date      TEXT,
            status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','cancelled')),
            account_id    INTEGER,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )
    """)

    # Transacciones: ingresos, egresos, transferencias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            type           TEXT NOT NULL CHECK (type IN ('income','expense','transfer')),
            date           TEXT NOT NULL,
            description    TEXT,
            amount         REAL NOT NULL,
            account_id     INTEGER,
            to_account_id  INTEGER,
            category_id    INTEGER,
            notes          TEXT,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id)    REFERENCES accounts(id),
            FOREIGN KEY(to_account_id) REFERENCES accounts(id),
            FOREIGN KEY(category_id)   REFERENCES categories(id)
        )
    """)

    # Inversiones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            currency        TEXT NOT NULL DEFAULT 'ARS' CHECK (currency IN ('ARS','USD')),
            initial_amount  REAL NOT NULL,
            current_amount  REAL NOT NULL,
            start_date      TEXT,
            notes           TEXT,
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Presupuestos mensuales
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id  INTEGER NOT NULL,
            month        TEXT NOT NULL,  -- YYYY-MM
            limit_amount REAL NOT NULL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, month),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)

    # Config inicial por defecto
    machine_id = _generate_machine_id()
    today = date.today().isoformat()

    existing = {row[0]: row[1] for row in cur.execute("SELECT key, value FROM config").fetchall()}
    if 'demo_install_date' not in existing:
        telemetry_date = _read_telemetry(machine_id)
        install_date = telemetry_date or today
        cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ('demo_install_date', install_date))
        if not telemetry_date:
            _write_telemetry(install_date, machine_id)

    defaults = {
        'version': 'DEMO',
        'license_tier': 'DEMO',
        'license_plan': 'DEMO',
        'license_key': '',
        'license_expires_at': '',
        'basica_activada': '0',
    }
    for key, value in defaults.items():
        if key not in existing:
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()
