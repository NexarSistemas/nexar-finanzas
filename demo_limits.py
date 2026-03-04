"""
demo_limits.py
Controla los límites de la versión DEMO y el estado de activación.
"""

# Límites de la versión DEMO
DEMO_LIMITS = {
    'expenses': 30,
    'incomes': 5,
    'bank_accounts': 4,
    'virtual_wallets': 4,
    'investments': 10,
}

DEMO_MESSAGE = (
    "Ha alcanzado el límite de la versión DEMO. "
    "Para continuar utilizando el sistema sin restricciones "
    "debe adquirir la versión completa."
)


def is_full_version(db_path: str) -> bool:
    """Verifica en la base de datos si el sistema está activado."""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE key = 'version'")
        row = cur.fetchone()
        conn.close()
        return row is not None and row[0] == 'FULL'
    except Exception:
        return False


def check_limit(db_path: str, resource: str, current_count: int) -> dict:
    """
    Verifica si se puede agregar un nuevo recurso.
    Retorna: {'allowed': bool, 'message': str, 'is_demo': bool}
    """
    if is_full_version(db_path):
        return {'allowed': True, 'message': '', 'is_demo': False}

    limit = DEMO_LIMITS.get(resource, 9999)
    if current_count >= limit:
        return {
            'allowed': False,
            'message': DEMO_MESSAGE,
            'is_demo': True,
            'limit': limit,
            'resource': resource
        }
    return {
        'allowed': True,
        'message': f'DEMO: {current_count + 1}/{limit}',
        'is_demo': True,
        'limit': limit
    }


def get_demo_status(db_path: str) -> dict:
    """Retorna el estado completo del modo demo."""
    import sqlite3
    if is_full_version(db_path):
        return {'is_demo': False, 'version': 'FULL', 'limits': {}}

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        counts = {}
        cur.execute("SELECT COUNT(*) FROM transactions WHERE type='expense'")
        counts['expenses'] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM transactions WHERE type='income'")
        counts['incomes'] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounts WHERE type='bank' AND active=1")
        counts['bank_accounts'] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounts WHERE type='virtual_wallet' AND active=1")
        counts['virtual_wallets'] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM investments")
        counts['investments'] = cur.fetchone()[0]
        conn.close()

        limits_info = {}
        for resource, count in counts.items():
            limit = DEMO_LIMITS.get(resource, 9999)
            limits_info[resource] = {
                'current': count,
                'limit': limit,
                'percent': round((count / limit) * 100) if limit > 0 else 0,
                'reached': count >= limit
            }

        return {'is_demo': True, 'version': 'DEMO', 'limits': limits_info, 'counts': counts}
    except Exception:
        return {'is_demo': True, 'version': 'DEMO', 'limits': {}}
