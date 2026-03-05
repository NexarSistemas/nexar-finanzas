"""
models.py
Inicialización y esquema de la base de datos SQLite.
Crea todas las tablas necesarias si no existen.
"""

import sqlite3
from datetime import date


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
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('app_name', 'Finanzas del Hogar')")
    cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('app_version', '1.6.0')")
    # Configuración de copias de seguridad automáticas
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_frecuencia', 'semanal')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_ultima_vez', '')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('backup_cantidad_max', '5')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('ai_api_key', '')")
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('ai_enabled', '1')")

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
