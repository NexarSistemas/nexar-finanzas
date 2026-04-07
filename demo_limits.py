"""
demo_limits.py
Sistema de tiers y límites por plan para Nexar Finanzas.

Planes:
  DEMO   — 30 días desde primera instalación, casi full con límites suaves
  BASICA — Pago único permanente, funciones limitadas
  PRO    — Suscripción mensual, acceso completo

Compatibilidad: check_limit(), is_full_version() y get_demo_status()
mantienen sus firmas originales para no romper routes.py ni templates.
"""

import sqlite3
from datetime import date


# ─── Límites por tier ─────────────────────────────────────────────────────────
#
# None = ilimitado
# int  = máximo permitido
#
# Recursos de cuentas: se cuentan como total global (3 en DEMO entre los 3 tipos)
# o como límite por tipo (1 de cada tipo en BASICA).
#
TIER_LIMITS = {
    'DEMO': {
        # Movimientos ilimitados
        'expenses':        None,
        'incomes':         None,
        # Cuentas: 3 en total entre los 3 tipos
        'bank_accounts':   3,
        'virtual_wallets': 3,
        'cash_accounts':   3,
        'accounts_total':  3,     # límite global compartido entre los 3 tipos
        # Inversiones
        'investments':     3,
        # Presupuestos ilimitados en DEMO
        'budgets':         None,
        # Reportes: full
        'reports_annual':  True,
        'reports_monthly': True,
        'reports_weekly':  True,
        # Inversiones: lectura + escritura
        'investments_write': True,
        # Actualizaciones
        'updates':         False,
    },
    'BASICA': {
        # Movimientos ilimitados
        'expenses':        None,
        'incomes':         None,
        # Cuentas: 1 por tipo
        'bank_accounts':   1,
        'virtual_wallets': 1,
        'cash_accounts':   1,
        'accounts_total':  None,  # sin límite global, el límite es por tipo
        # Inversiones: solo lectura
        'investments':     None,  # no bloquea al contar, se bloquea por flag
        'investments_write': False,
        # Presupuestos: máximo 3
        'budgets':         3,
        # Reportes: semanal + mensual (sin anual)
        'reports_annual':  False,
        'reports_monthly': True,
        'reports_weekly':  True,
        # Actualizaciones
        'updates':         False,
    },
    'PRO': {
        # Todo ilimitado
        'expenses':        None,
        'incomes':         None,
        'bank_accounts':   None,
        'virtual_wallets': None,
        'cash_accounts':   None,
        'accounts_total':  None,
        'investments':     None,
        'investments_write': True,
        'budgets':         None,
        'reports_annual':  True,
        'reports_monthly': True,
        'reports_weekly':  True,
        'updates':         True,
    },
}

# Mensajes por tier
_MSG_DEMO_VENCIDA = (
    "Tu período de prueba de 30 días ha vencido. "
    "Podés seguir viendo tus datos pero no agregar nuevos registros. "
    "Adquirí el Plan Básico para continuar."
)

_MSG_LIMITE = (
    "Alcanzaste el límite de tu plan actual. "
    "Actualizá tu plan para agregar más."
)


# ─── Función principal de tier ────────────────────────────────────────────────

def get_tier(db_path: str) -> str:
    """
    Retorna el tier activo: 'DEMO' | 'BASICA' | 'PRO'

    Lógica:
      - Si license_tier = 'PRO' y expires_at venció → retorna 'BASICA'
        (no cae a DEMO, preserva todos los datos)
      - Si demo_install_date tiene más de 30 días → DEMO vencida
        (retorna 'DEMO_EXPIRED', que los checks tratan como bloqueado)
      - Resto: retorna el tier guardado en la BD
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()

        tier_row    = cur.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        expires_row = cur.execute("SELECT value FROM config WHERE key='license_expires_at'").fetchone()
        install_row = cur.execute("SELECT value FROM config WHERE key='demo_install_date'").fetchone()
        conn.close()

        tier       = tier_row[0]    if tier_row    else 'DEMO'
        expires_at = expires_row[0] if expires_row else ''
        install_dt = install_row[0] if install_row else ''

        # PRO vencido → baja a BASICA (nunca a DEMO)
        if tier == 'PRO' and expires_at:
            try:
                if date.today() > date.fromisoformat(expires_at):
                    return 'BASICA'
            except Exception:
                pass

        # DEMO: verificar si venció (30 días)
        if tier == 'DEMO' and install_dt:
            try:
                delta = (date.today() - date.fromisoformat(install_dt)).days
                if delta > 30:
                    return 'DEMO_EXPIRED'
            except Exception:
                pass

        return tier

    except Exception:
        return 'DEMO'


def is_pro_expired(db_path: str) -> bool:
    """
    True si tenía PRO pero venció y bajó a BASICA.
    Útil para mostrar el aviso de renovación en los templates.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        tier_row    = cur.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        expires_row = cur.execute("SELECT value FROM config WHERE key='license_expires_at'").fetchone()
        conn.close()

        if not tier_row or tier_row[0] != 'PRO':
            return False
        expires_at = expires_row[0] if expires_row else ''
        if not expires_at:
            return False
        return date.today() > date.fromisoformat(expires_at)
    except Exception:
        return False


def get_demo_days_remaining(db_path: str) -> int | None:
    """
    Retorna días restantes de demo, o None si no es DEMO o ya venció.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        tier_row    = cur.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        install_row = cur.execute("SELECT value FROM config WHERE key='demo_install_date'").fetchone()
        conn.close()

        if not tier_row or tier_row[0] != 'DEMO':
            return None
        if not install_row or not install_row[0]:
            return 30

        delta = (date.today() - date.fromisoformat(install_row[0])).days
        remaining = 30 - delta
        return max(0, remaining)
    except Exception:
        return None

def get_pro_days_remaining(db_path: str) -> int | None:
    """
    Retorna los días restantes de la suscripción PRO.
    Retorna None si el tier no es PRO o no hay fecha de vencimiento.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        tier_row    = cur.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        expires_row = cur.execute("SELECT value FROM config WHERE key='license_expires_at'").fetchone()
        conn.close()

        if not tier_row or tier_row[0] != 'PRO':
            return None
        
        expires_at = expires_row[0] if expires_row else ''
        if not expires_at:
            return None

        # Cálculo de diferencia de días
        delta = (date.fromisoformat(expires_at) - date.today()).days
        return delta
    except Exception:
        return None


# ─── Verificaciones de límites ────────────────────────────────────────────────

def check_limit(db_path: str, resource: str, current_count: int) -> dict:
    """
    Verifica si se puede agregar un nuevo recurso según el tier activo.

    Firma idéntica al original para compatibilidad con routes.py.
    Retorna: {'allowed': bool, 'message': str, 'is_demo': bool, ...}

    Recursos reconocidos:
      expenses, incomes, bank_accounts, virtual_wallets,
      cash_accounts, investments, budgets
    """
    tier = get_tier(db_path)

    # DEMO vencida: modo lectura total, nada permitido
    if tier == 'DEMO_EXPIRED':
        return {
            'allowed':  False,
            'message':  _MSG_DEMO_VENCIDA,
            'is_demo':  True,
            'is_expired': True,
            'limit':    0,
            'resource': resource,
        }

    limits = TIER_LIMITS.get(tier, TIER_LIMITS['DEMO'])

    # Inversiones: en BASICA solo lectura (no se puede agregar nada)
    if resource == 'investments' and not limits.get('investments_write', True):
        return {
            'allowed':  False,
            'message':  'Las inversiones están disponibles en modo lectura en el Plan Básico. '
                        'Actualizá al Plan Pro para registrar operaciones.',
            'is_demo':  False,
            'is_basica_readonly': True,
            'limit':    0,
            'resource': resource,
        }

    # Para cuentas en DEMO: límite global compartido entre los 3 tipos
    if resource in ('bank_accounts', 'virtual_wallets', 'cash_accounts') and tier == 'DEMO':
        total_limit = limits.get('accounts_total')
        if total_limit is not None:
            # Contar el total de cuentas activas de todos los tipos
            try:
                conn = sqlite3.connect(db_path)
                total_actual = conn.execute(
                    "SELECT COUNT(*) FROM accounts WHERE active=1"
                ).fetchone()[0]
                conn.close()
            except Exception:
                total_actual = current_count

            if total_actual >= total_limit:
                return {
                    'allowed':  False,
                    'message':  f'Límite DEMO: máximo {total_limit} cuentas en total. '
                                f'Tenés {total_actual}. Activá un plan para agregar más.',
                    'is_demo':  True,
                    'limit':    total_limit,
                    'resource': resource,
                }
            return {
                'allowed': True,
                'message': f'DEMO: {total_actual + 1}/{total_limit} cuentas',
                'is_demo': True,
                'limit':   total_limit,
            }

    # Límite estándar por recurso
    limit = limits.get(resource)

    if limit is None:
        # Sin límite para este tier
        return {
            'allowed': True,
            'message': '',
            'is_demo': tier in ('DEMO', 'DEMO_EXPIRED'),
        }

    if current_count >= limit:
        tier_label = 'DEMO' if tier == 'DEMO' else 'Plan Básico'
        return {
            'allowed':  False,
            'message':  f'Límite {tier_label}: máximo {limit}. '
                        f'{_MSG_LIMITE}',
            'is_demo':  tier in ('DEMO', 'DEMO_EXPIRED'),
            'limit':    limit,
            'resource': resource,
        }

    return {
        'allowed': True,
        'message': f'{tier}: {current_count + 1}/{limit}',
        'is_demo': tier in ('DEMO', 'DEMO_EXPIRED'),
        'limit':   limit,
    }


# ─── Estado completo ──────────────────────────────────────────────────────────

def is_full_version(db_path: str) -> bool:
    """
    Retorna True si el sistema está activado (BASICA o PRO).

    Firma idéntica al original para compatibilidad con routes.py.
    PRO vencido retorna True porque el usuario sigue en BASICA, no en DEMO.
    """
    tier = get_tier(db_path)
    return tier in ('BASICA', 'PRO')


def get_demo_status(db_path: str) -> dict:
    """
    Retorna el estado completo del plan activo.

    Firma idéntica al original para compatibilidad con routes.py y templates.
    Campos garantizados: is_demo, version, limits, counts.

    Nuevo campo: tier (DEMO/DEMO_EXPIRED/BASICA/PRO)
    """
    tier = get_tier(db_path)

    # ── Contar recursos actuales ──────────────────────────────────────────────
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()

        counts = {
            'expenses':        cur.execute(
                "SELECT COUNT(*) FROM transactions WHERE type='expense'"
            ).fetchone()[0],
            'incomes':         cur.execute(
                "SELECT COUNT(*) FROM transactions WHERE type='income'"
            ).fetchone()[0],
            'bank_accounts':   cur.execute(
                "SELECT COUNT(*) FROM accounts WHERE type='bank' AND active=1"
            ).fetchone()[0],
            'virtual_wallets': cur.execute(
                "SELECT COUNT(*) FROM accounts WHERE type='virtual_wallet' AND active=1"
            ).fetchone()[0],
            'cash_accounts':   cur.execute(
                "SELECT COUNT(*) FROM accounts WHERE type='cash' AND active=1"
            ).fetchone()[0],
            'investments':     cur.execute(
                "SELECT COUNT(*) FROM investments"
            ).fetchone()[0],
            'budgets':         cur.execute(
                "SELECT COUNT(*) FROM budgets"
            ).fetchone()[0],
        }
        conn.close()
    except Exception:
        counts = {k: 0 for k in (
            'expenses', 'incomes', 'bank_accounts', 'virtual_wallets',
            'cash_accounts', 'investments', 'budgets'
        )}

    # ── Armar límites con porcentaje de uso ───────────────────────────────────
    limits = TIER_LIMITS.get(tier if tier != 'DEMO_EXPIRED' else 'DEMO',
                             TIER_LIMITS['DEMO'])

    # Para DEMO: el límite de cuentas es total global de 3
    limits_info = {}
    for resource, count in counts.items():
        if resource in ('expenses', 'incomes'):
            # Siempre ilimitados (todos los planes)
            limits_info[resource] = {
                'current': count, 'limit': None,
                'percent': 0,     'reached': False,
            }
            continue

        if resource in ('bank_accounts', 'virtual_wallets', 'cash_accounts') and tier in ('DEMO', 'DEMO_EXPIRED'):
            total_limit = limits.get('accounts_total', 3)
            total_actual = counts['bank_accounts'] + counts['virtual_wallets'] + counts['cash_accounts']
            limits_info[resource] = {
                'current': count,
                'limit':   total_limit,
                'percent': round(total_actual / total_limit * 100) if total_limit else 0,
                'reached': total_actual >= total_limit,
            }
            continue

        limit = limits.get(resource)
        if limit is None:
            limits_info[resource] = {
                'current': count, 'limit': None,
                'percent': 0,     'reached': False,
            }
        else:
            limits_info[resource] = {
                'current': count,
                'limit':   limit,
                'percent': round((count / limit) * 100) if limit > 0 else 0,
                'reached': count >= limit,
            }

    # ── Días restantes de demo ────────────────────────────────────────────────
    demo_days = get_demo_days_remaining(db_path)
    pro_days  = get_pro_days_remaining(db_path)

    # ── Determinar versión para templates ─────────────────────────────────────
    # 'version' se usa en base.html para el badge (DEMO/FULL)
    # Mantenemos compatibilidad: DEMO/DEMO_EXPIRED → 'DEMO', resto → tier real
    if tier in ('DEMO', 'DEMO_EXPIRED'):
        version_label = 'DEMO'
        is_demo_flag  = True
    else:
        version_label = tier   # 'BASICA' o 'PRO'
        is_demo_flag  = False

    return {
        # Campos originales — compatibilidad garantizada
        'is_demo':   is_demo_flag,
        'version':   version_label,
        'limits':    limits_info,
        'counts':    counts,
        # Campos nuevos para templates actualizados
        'tier':           tier,               # DEMO/DEMO_EXPIRED/BASICA/PRO
        'is_expired':     tier == 'DEMO_EXPIRED',
        'is_basica':      tier == 'BASICA',
        'is_pro':         tier == 'PRO',
        'pro_expired':    is_pro_expired(db_path),
        'demo_days':      demo_days,          # int o None
        'pro_days':       pro_days,           # int o None
        'pro_expires_soon':     pro_days == 5,
        'pro_expires_tomorrow': pro_days == 1,
        'can_update':     limits.get('updates', False),
        'can_investments_write': limits.get('investments_write', True),
    }
