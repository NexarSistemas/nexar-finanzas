"""
models.py
Inicialización y esquema de la base de datos SQLite.
Crea todas las tablas necesarias si no existen.
"""

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

    # ── Migración segura: agregar UNIQUE si la tabla ya existe sin él ───────────
    # Verificar si ya tiene la restricción unique comprobando si existe el índice
    cur.execute("""
        SELECT COUNT(*) as n FROM sqlite_master
        WHERE type='index' AND tbl_name='categories'
        AND sql LIKE '%UNIQUE%'
    """)
    tiene_unique = cur.fetchone()[0] > 0

    if not tiene_unique:
        # 1. Limpiar duplicados: conservar el de menor id por cada (name, type)
        cur.execute("""
            DELETE FROM categories
            WHERE id NOT IN (
                SELECT MIN(id) FROM categories GROUP BY name, type
            )
        """)
        # 2. Recrear la tabla con la restricción UNIQUE y migrar los datos limpios.
        #    Deshabilitamos foreign keys temporalmente para poder hacer DROP TABLE
        #    sin que falle por las referencias desde transactions/budgets.
        #    PRAGMA foreign_keys debe ejecutarse fuera de una transacción activa.
        conn.commit()                            # cerrar transacción activa
        conn.execute("PRAGMA foreign_keys = OFF")  # desactivar en la conexión
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories_new (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                type         TEXT NOT NULL CHECK (type IN ('income','expense')),
                active       INTEGER NOT NULL DEFAULT 1,
                es_necesario INTEGER NOT NULL DEFAULT 1,
                UNIQUE(name, type)
            )
        """)
        cur.execute("""
            INSERT OR IGNORE INTO categories_new (id, name, type, active, es_necesario)
            SELECT id, name, type, active, COALESCE(es_necesario, 1) FROM categories
        """)
        cur.execute("DROP TABLE categories")
        cur.execute("ALTER TABLE categories_new RENAME TO categories")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")  # reactivar

    # Transacciones: ingresos y gastos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL CHECK (type IN ('income','expense')),
            amount      REAL NOT NULL CHECK (amount > 0),
            currency    TEXT NOT NULL DEFAULT 'ARS',
            category_id INTEGER REFERENCES categories(id),
            account_id  INTEGER REFERENCES accounts(id),
            method      TEXT CHECK (method IN ('cash','debit','credit','transfer','virtual')),
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Transferencias entre cuentas propias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account_id INTEGER REFERENCES accounts(id),
            to_account_id   INTEGER REFERENCES accounts(id),
            amount          REAL NOT NULL CHECK (amount > 0),
            currency        TEXT NOT NULL DEFAULT 'ARS',
            date            TEXT NOT NULL,
            description     TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Presupuestos mensuales por categoría
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id),
            amount      REAL NOT NULL CHECK (amount > 0),
            month       INTEGER NOT NULL,
            year        INTEGER NOT NULL,
            UNIQUE (category_id, month, year)
        )
    """)

    # Inversiones: acciones, cripto, bonos, FCI, etc.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_type       TEXT NOT NULL,
            asset_name       TEXT NOT NULL,
            ticker           TEXT,
            transaction_type TEXT NOT NULL CHECK (transaction_type IN ('buy','sell')),
            quantity         REAL NOT NULL CHECK (quantity > 0),
            price            REAL NOT NULL CHECK (price > 0),
            currency         TEXT NOT NULL DEFAULT 'ARS',
            date             TEXT NOT NULL,
            notes            TEXT,
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Caché de precios de mercado actualizados por activo
    cur.execute("""
        CREATE TABLE IF NOT EXISTS precios_mercado (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name    TEXT NOT NULL,
            ticker        TEXT,
            precio_actual REAL,
            variacion_dia REAL,
            moneda        TEXT NOT NULL DEFAULT 'ARS',
            fuente        TEXT,
            updated_at    TEXT,
            UNIQUE(asset_name)
        )
    """)

    # Última cotización del dólar (cache heredado — se mantiene para compatibilidad)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usd_rate (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            oficial    REAL,
            blue       REAL,
            updated_at TEXT
        )
    """)

    # Caché de cotizaciones completas (dólar, euro, cripto) en formato JSON
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotizaciones_cache (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            datos_json TEXT,
            updated_at TEXT
        )
    """)

    # Precios de mercado actualizados automáticamente para inversiones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS precios_mercado (
            asset_name   TEXT PRIMARY KEY,
            ticker       TEXT,
            precio_actual REAL,
            variacion_dia REAL,
            moneda       TEXT DEFAULT 'ARS',
            fuente       TEXT,
            updated_at   TEXT
        )
    """)

    # Agregar columna ticker a investments si no existe (migración segura)
    try:
        cur.execute("ALTER TABLE investments ADD COLUMN ticker TEXT")
    except Exception:
        pass  # Ya existe, ignorar

    # Índices para mejorar performance en consultas frecuentes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_date      ON transactions(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_type      ON transactions(type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_category  ON transactions(category_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_account   ON transactions(account_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_month ON budgets(year, month)")

    # ── Datos iniciales ────────────────────────────────────────────────────────

    # Versión por defecto: DEMO
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('version', 'DEMO')")
    cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('app_name', 'Nexar Finanzas')") #
    cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('app_version', '1.10.7')") #
    # Configuración de copias de seguridad automáticas
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_frecuencia', 'semanal')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_ultima_vez', '')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_cantidad_max', '5')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('ai_api_key', '')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('ai_enabled', '1')")
    # ── Sistema de licencias por tiers ────────────────────────────────────────
    # license_tier:       'DEMO' | 'BASICA' | 'PRO'
    # license_expires_at: fecha ISO de vencimiento PRO (vacío = no vence)
    # demo_install_date:  fecha ISO de primera instalación (gestionada por anti-reinstall)
    # machine_id:         hardware ID del equipo (gestionado más abajo)
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('license_tier', 'DEMO')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('license_expires_at', '')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('demo_install_date', '')")

    # Categorías de gastos predeterminadas: (nombre, es_necesario)
    # 1 = necesario (básico para vivir), 0 = prescindible (opcional)
    default_expense_cats = [
        ('Alimentación',       1),
        ('Transporte',         1),
        ('Servicios',          1),
        ('Alquiler/Hipoteca',  1),
        ('Salud',              1),
        ('Educación',          1),
        ('Entretenimiento',    0),
        ('Ropa',               0),
        ('Tecnología',         0),
        ('Otros gastos',       1),
    ]
    for cat_name, es_nec in default_expense_cats:
        cur.execute(
            "INSERT OR IGNORE INTO categories (name, type, es_necesario) VALUES (?, 'expense', ?)",
            (cat_name, es_nec)
        )
        # Actualizar el flag en bases existentes que ya tienen la categoría sin clasificar
        cur.execute(
            """UPDATE categories SET es_necesario=?
               WHERE name=? AND type='expense'
               AND es_necesario=1
               AND ? = 0""",
            (es_nec, cat_name, es_nec)
        )

    # Categorías de ingresos predeterminadas
    default_income_cats = [
        'Sueldo', 'Freelance', 'Alquiler cobrado', 'Inversiones', 'Otros ingresos'
    ]
    for cat in default_income_cats:
        cur.execute(
            "INSERT OR IGNORE INTO categories (name, type) VALUES (?, 'income')",
            (cat,)
        )

    # ── Machine ID — generar si no existe ─────────────────────────────────────
    # Se genera una sola vez y se persiste. Identifica este equipo de forma única.
    _mid_row = cur.execute("SELECT value FROM config WHERE key='machine_id'").fetchone()
    if not _mid_row or not _mid_row[0]:
        _new_mid = _generate_machine_id()
        cur.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('machine_id', ?)",
            (_new_mid,)
        )
        _mid = _new_mid
    else:
        _mid = _mid_row[0]

    # ── Anti-reinstall: demo_install_date ─────────────────────────────────────
    # Lógica de 3 casos:
    #   1. telemetry.bin existe y es válido → es la fuente de verdad
    #      Si la DB fue borrada y la fecha difiere, se restaura la original
    #   2. Solo la DB tiene fecha (post-update o primer arranque post-v1.9.x)
    #      → crear el archivo externo con esa fecha
    #   3. Ninguno tiene fecha → primera instalación real
    #      → guardar hoy en DB y en archivo externo
    _telem_date = _read_telemetry(_mid)
    _inst_row   = cur.execute(
        "SELECT value FROM config WHERE key='demo_install_date'"
    ).fetchone()
    _db_date = _inst_row[0] if _inst_row and _inst_row[0] else None

    if _telem_date:
        # Archivo externo es fuente de verdad: restaurar BD si fue borrada
        if _db_date != _telem_date:
            cur.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES ('demo_install_date', ?)",
                (_telem_date,)
            )
    elif _db_date:
        # BD tiene fecha pero archivo no existe → crear archivo
        _write_telemetry(_db_date, _mid)
    else:
        # Primera instalación real
        _today = date.today().isoformat()
        cur.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('demo_install_date', ?)",
            (_today,)
        )
        _write_telemetry(_today, _mid)

    # ── Migración silenciosa: usuarios con código HMAC viejo ──────────────────
    # Si version='FULL' pero license_tier es 'DEMO' o no existe, el usuario activó
    # con el sistema HMAC anterior (XXXX-XXXX-XXXX-XXXX). Se los migra a BASICA
    # permanente sin pedirles nada. Sus datos y activación siguen funcionando.
    _ver_row  = cur.execute("SELECT value FROM config WHERE key='version'").fetchone()
    _tier_row = cur.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
    if (_ver_row and _ver_row[0] == 'FULL' and
            (_tier_row is None or _tier_row[0] == 'DEMO')):
        cur.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('license_tier', 'BASICA')"
        )

    conn.commit()
    conn.close()


def recalculate_account_balance(conn: sqlite3.Connection, account_id: int):
    """Recalcula el saldo actual de una cuenta basado en transacciones y transferencias."""
    cur = conn.cursor()

    # Saldo inicial
    cur.execute("SELECT initial_balance FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    if not row:
        return
    balance = row['initial_balance']

    # Sumar ingresos a esta cuenta
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id=? AND type='income'",
        (account_id,)
    )
    balance += cur.fetchone()[0]

    # Restar gastos de esta cuenta
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id=? AND type='expense'",
        (account_id,)
    )
    balance -= cur.fetchone()[0]

    # Restar transferencias salientes
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE from_account_id=?",
        (account_id,)
    )
    balance -= cur.fetchone()[0]

    # Sumar transferencias entrantes
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE to_account_id=?",
        (account_id,)
    )
    balance += cur.fetchone()[0]

    cur.execute("UPDATE accounts SET current_balance=? WHERE id=?", (balance, account_id))
