"""
services.py
Lógica de negocio: reportes, cálculos de presupuesto, gráficos, cotización USD.
"""

import sqlite3
import os
import io
import csv
from datetime import date, datetime
from models import get_db, recalculate_account_balance


# ─── Reportes ──────────────────────────────────────────────────────────────────

def get_monthly_summary(db_path: str, year: int, month: int) -> dict:
    """Genera resumen de ingresos, gastos y balance para un mes."""
    conn = get_db(db_path)
    cur = conn.cursor()
    period = f"{year:04d}-{month:02d}"

    cur.execute("""
        SELECT type, currency, COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY type, currency
    """, (period,))
    rows = cur.fetchall()

    summary = {'income': {}, 'expense': {}, 'balance': {}}
    for row in rows:
        summary[row['type']][row['currency']] = row['total']

    # Balance por moneda
    for currency in set(list(summary['income'].keys()) + list(summary['expense'].keys())):
        inc = summary['income'].get(currency, 0)
        exp = summary['expense'].get(currency, 0)
        summary['balance'][currency] = inc - exp

    # Por categoría
    cur.execute("""
        SELECT c.name, t.type, t.currency, COALESCE(SUM(t.amount), 0) as total
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE strftime('%Y-%m', t.date) = ?
        GROUP BY c.name, t.type, t.currency
        ORDER BY total DESC
    """, (period,))
    summary['by_category'] = [dict(r) for r in cur.fetchall()]

    # Top gastos por categoría
    cur.execute("""
        SELECT c.name, COALESCE(SUM(t.amount), 0) as total
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE strftime('%Y-%m', t.date) = ? AND t.type = 'expense' AND t.currency = 'ARS'
        GROUP BY c.name
        ORDER BY total DESC
        LIMIT 8
    """, (period,))
    summary['top_expenses'] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return summary


def get_annual_summary(db_path: str, year: int) -> list:
    """Resumen mensual de todo un año."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT strftime('%m', date) as month, type, currency,
               COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE strftime('%Y', date) = ?
        GROUP BY month, type, currency
        ORDER BY month
    """, (str(year),))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_weekly_summary(db_path: str) -> dict:
    """Resumen de los últimos 7 días."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT type, currency, COALESCE(SUM(amount), 0) as total,
               strftime('%Y-%m-%d', date) as day
        FROM transactions
        WHERE date >= date('now', '-7 days')
        GROUP BY type, currency, day
        ORDER BY day
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ─── Presupuesto y Alertas ─────────────────────────────────────────────────────

def get_budget_status(db_path: str, year: int, month: int) -> list:
    """
    Retorna estado de presupuestos del mes.
    Nivel de alerta: 'ok' < 80%, 'warning' >= 80%, 'danger' >= 100%
    """
    conn = get_db(db_path)
    cur = conn.cursor()
    period = f"{year:04d}-{month:02d}"

    cur.execute("""
        SELECT b.id, c.name as category, b.amount as budget,
               COALESCE(
                   (SELECT SUM(t.amount) FROM transactions t
                    WHERE t.category_id = b.category_id
                    AND t.type = 'expense'
                    AND strftime('%Y-%m', t.date) = ?), 0
               ) as spent
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        WHERE b.year = ? AND b.month = ?
        ORDER BY c.name
    """, (period, year, month))

    results = []
    for row in cur.fetchall():
        r = dict(row)
        pct = (r['spent'] / r['budget'] * 100) if r['budget'] > 0 else 0
        r['percent'] = round(pct, 1)
        r['remaining'] = max(0, r['budget'] - r['spent'])
        if pct >= 100:
            r['status'] = 'danger'
            r['status_label'] = '🔴 Excedido'
        elif pct >= 80:
            r['status'] = 'warning'
            r['status_label'] = '🟡 Advertencia'
        else:
            r['status'] = 'ok'
            r['status_label'] = '🟢 Normal'
        results.append(r)

    conn.close()
    return results


# ─── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard_data(db_path: str) -> dict:
    """Datos para la pantalla principal."""
    conn = get_db(db_path)
    cur = conn.cursor()
    today = date.today()
    period = f"{today.year:04d}-{today.month:02d}"

    # Saldos de cuentas activas
    cur.execute("""
        SELECT id, name, type, currency, current_balance
        FROM accounts WHERE active = 1
        ORDER BY type, name
    """)
    accounts = [dict(r) for r in cur.fetchall()]

    # Totales del mes actual
    cur.execute("""
        SELECT type, currency, COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY type, currency
    """, (period,))
    month_totals = {}
    for row in cur.fetchall():
        key = f"{row['type']}_{row['currency']}"
        month_totals[key] = row['total']

    # Últimas 5 transacciones
    cur.execute("""
        SELECT t.*, c.name as category_name, a.name as account_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        ORDER BY t.date DESC, t.id DESC
        LIMIT 5
    """)
    recent = [dict(r) for r in cur.fetchall()]

    # Alertas de presupuesto activas
    budget_alerts = [
        b for b in get_budget_status(db_path, today.year, today.month)
        if b['status'] in ('warning', 'danger')
    ]

    # Cotización USD
    cur.execute("SELECT oficial, blue, updated_at FROM usd_rate WHERE id = 1")
    usd_row = cur.fetchone()
    usd = dict(usd_row) if usd_row else None

    conn.close()
    return {
        'accounts': accounts,
        'month_totals': month_totals,
        'recent_transactions': recent,
        'budget_alerts': budget_alerts,
        'usd': usd,
        'period': period,
        'today': today.isoformat(),
    }


# ─── Datos para gráficos (Chart.js en el browser — sin dependencias) ──────────

def get_monthly_chart_data(db_path: str, year: int, month: int) -> dict:
    """Devuelve JSON con datos para el gráfico de torta mensual."""
    conn = get_db(db_path)
    period = f"{year:04d}-{month:02d}"
    rows = conn.execute("""
        SELECT c.name, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE strftime('%Y-%m', t.date) = ? AND t.type = 'expense' AND t.currency = 'ARS'
        GROUP BY c.name HAVING total > 0 ORDER BY total DESC LIMIT 8
    """, (period,)).fetchall()
    conn.close()
    colors = ['#0d6efd','#dc3545','#198754','#fd7e14','#6f42c1',
              '#20c997','#ffc107','#0dcaf0']
    return {
        'labels': [r['name'] for r in rows],
        'values': [round(r['total'], 2) for r in rows],
        'colors': colors[:len(rows)],
    }


def get_annual_chart_data(db_path: str, year: int) -> dict:
    """Devuelve JSON con datos para el gráfico de barras anual."""
    rows = get_annual_summary(db_path, year)
    month_names = ['Ene','Feb','Mar','Abr','May','Jun',
                   'Jul','Ago','Sep','Oct','Nov','Dic']
    income_vals  = [0.0] * 12
    expense_vals = [0.0] * 12
    for r in rows:
        if r['currency'] == 'ARS':
            m = int(r['month']) - 1
            if r['type'] == 'income':
                income_vals[m]  += r['total']
            else:
                expense_vals[m] += r['total']
    return {
        'labels':   month_names,
        'ingresos': [round(v, 2) for v in income_vals],
        'gastos':   [round(v, 2) for v in expense_vals],
    }


# ─── Exportación CSV ───────────────────────────────────────────────────────────

def export_transactions_csv(db_path: str, year: int = None, month: int = None) -> str:
    """Exporta transacciones a CSV. Retorna contenido como string."""
    conn = get_db(db_path)
    cur = conn.cursor()

    query = """
        SELECT t.date, t.type, c.name as category, t.amount, t.currency,
               t.method, a.name as account, t.description
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
    """
    params = []
    if year and month:
        query += " WHERE strftime('%Y-%m', t.date) = ?"
        params.append(f"{year:04d}-{month:02d}")
    elif year:
        query += " WHERE strftime('%Y', t.date) = ?"
        params.append(str(year))
    query += " ORDER BY t.date DESC, t.id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Fecha', 'Tipo', 'Categoría', 'Monto', 'Moneda',
                     'Método', 'Cuenta', 'Descripción'])
    for row in rows:
        writer.writerow([
            row['date'], 'Ingreso' if row['type'] == 'income' else 'Gasto',
            row['category'] or '', row['amount'], row['currency'],
            row['method'] or '', row['account'] or '', row['description'] or ''
        ])
    return output.getvalue()


# ─── Cotización USD ────────────────────────────────────────────────────────────

def fetch_usd_rate(db_path: str) -> dict:
    """Intenta obtener cotización del dólar. No bloquea si falla."""
    try:
        import urllib.request
        import json
        url = "https://dolarapi.com/v1/dolares/oficial"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            oficial = data.get('venta', 0)

        url2 = "https://dolarapi.com/v1/dolares/blue"
        with urllib.request.urlopen(url2, timeout=5) as resp2:
            data2 = json.loads(resp2.read())
            blue = data2.get('venta', 0)

        # Guardar en DB
        conn = get_db(db_path)
        conn.execute("""
            INSERT OR REPLACE INTO usd_rate (id, oficial, blue, updated_at)
            VALUES (1, ?, ?, datetime('now','localtime'))
        """, (oficial, blue))
        conn.commit()
        conn.close()
        return {'oficial': oficial, 'blue': blue, 'error': None}
    except Exception as e:
        # Retornar última cotización guardada
        try:
            conn = get_db(db_path)
            cur = conn.cursor()
            cur.execute("SELECT oficial, blue, updated_at FROM usd_rate WHERE id=1")
            row = cur.fetchone()
            conn.close()
            if row:
                return {'oficial': row['oficial'], 'blue': row['blue'],
                        'updated_at': row['updated_at'], 'cached': True}
        except Exception:
            pass
        return {'oficial': None, 'blue': None, 'error': str(e)}


# ─── Inversiones ───────────────────────────────────────────────────────────────

# Mapeo automático de ticker por tipo de activo
# Si el usuario no ingresa ticker, el sistema lo intenta deducir del nombre
_TICKER_HINTS = {
    # Criptomonedas → IDs de CoinGecko
    'bitcoin': 'bitcoin', 'btc': 'bitcoin',
    'ethereum': 'ethereum', 'eth': 'ethereum',
    'tether': 'tether', 'usdt': 'tether',
    'binancecoin': 'binancecoin', 'bnb': 'binancecoin',
    'ripple': 'ripple', 'xrp': 'ripple',
    'solana': 'solana', 'sol': 'solana',
    'cardano': 'cardano', 'ada': 'cardano',
    'polkadot': 'polkadot', 'dot': 'polkadot',
}

# Fuentes disponibles por tipo de activo
_FUENTES = {
    'Acciones':         'yahoo',      # Yahoo Finance (.BA para argentinas, sin sufijo para USA)
    'CEDEAR':           'yahoo',      # Yahoo Finance con sufijo .BA
    'Bonos':            'byma',       # BYMA open data
    'FCI':              'cafci',      # API CAFCI Argentina
    'Cripto':           'coingecko',  # CoinGecko
    'Plazo fijo':       None,         # No aplica precio de mercado
    'Otro':             'yahoo',      # Intento con Yahoo
}


def fetch_precio_yahoo(ticker: str) -> dict | None:
    """
    Obtiene precio actual desde Yahoo Finance (gratuito, sin registro).
    Soporta: acciones USA (AAPL), argentinas (GGAL.BA), CEDEARs (TSLA.BA).
    """
    import urllib.request, json
    try:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?interval=1d&range=1d")
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 FinanzasHogar/1.2'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        result = data['chart']['result'][0]
        meta   = result['meta']
        precio = meta.get('regularMarketPrice') or meta.get('previousClose', 0)
        prev   = meta.get('chartPreviousClose') or meta.get('previousClose', precio)
        moneda = meta.get('currency', 'ARS')
        var_dia = ((precio - prev) / prev * 100) if prev else 0
        return {
            'precio':    round(precio, 4),
            'variacion': round(var_dia, 2),
            'moneda':    moneda,
            'fuente':    'Yahoo Finance',
        }
    except Exception:
        return None


def fetch_precio_coingecko(coingecko_id: str) -> dict | None:
    """Precio cripto desde CoinGecko (gratuita, sin API key)."""
    import urllib.request, json
    try:
        url = (f"https://api.coingecko.com/api/v3/simple/price"
               f"?ids={coingecko_id}&vs_currencies=usd&include_24hr_change=true")
        req = urllib.request.Request(url, headers={'User-Agent': 'FinanzasHogar/1.2'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if coingecko_id in data:
            precio = data[coingecko_id].get('usd', 0)
            var    = data[coingecko_id].get('usd_24h_change', 0)
            return {
                'precio':    round(precio, 6),
                'variacion': round(var or 0, 2),
                'moneda':    'USD',
                'fuente':    'CoinGecko',
            }
    except Exception:
        return None


def fetch_precio_byma(ticker: str) -> dict | None:
    """
    Precio de bonos/acciones desde BYMA Open Data (gratuito, sin registro).
    Endpoint público oficial de Bolsas y Mercados Argentinos.
    """
    import urllib.request, json
    try:
        # BYMA free endpoint para datos de panel
        url = ("https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/"
               "free/bigboard-request")
        payload = json.dumps({
            "excludeZeroPxAndQty": True,
            "T2": True, "T1": False, "T0": False,
            "Content-Type": "application/json"
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            'Content-Type': 'application/json',
            'User-Agent':   'FinanzasHogar/1.2',
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        items = data.get('data', [])
        ticker_up = ticker.upper()
        for item in items:
            simbolo = (item.get('descripcionAbreviada') or
                       item.get('simbolo') or '').upper()
            if simbolo == ticker_up:
                precio = item.get('ultimoPrecio') or item.get('precioAjuste', 0)
                var    = item.get('variacion', 0)
                return {
                    'precio':    round(float(precio), 4),
                    'variacion': round(float(var or 0), 2),
                    'moneda':    'ARS',
                    'fuente':    'BYMA',
                }
    except Exception:
        pass
    return None


def fetch_precio_fci(nombre_fci: str) -> dict | None:
    """
    Precio de cuotapartes de FCI desde la API de CAFCI (gratuita, sin registro).
    Busca por nombre parcial del fondo.
    """
    import urllib.request, json
    try:
        # Listar fondos y buscar por nombre
        url_fondos = ("https://api.cafci.org.ar/fondo?"
                      "estado=1&populate=regenteFondo,tipoFondo,clase")
        req = urllib.request.Request(url_fondos, headers={
            'User-Agent': 'FinanzasHogar/1.2'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        fondos = data.get('data', [])
        nombre_buscar = nombre_fci.lower().strip()
        fondo_encontrado = None
        for fondo in fondos:
            nombre_api = (fondo.get('nombre') or '').lower()
            if nombre_buscar in nombre_api or nombre_api in nombre_buscar:
                fondo_encontrado = fondo
                break
        if not fondo_encontrado:
            return None
        # Obtener última cuotaparte
        fondo_id = fondo_encontrado.get('id')
        clase_id = None
        clases = fondo_encontrado.get('clase', [])
        if clases:
            clase_id = clases[0].get('id')
        if not fondo_id or not clase_id:
            return None
        url_cp = f"https://api.cafci.org.ar/fondo/{fondo_id}/clase/{clase_id}/cuotaparte?limit=1"
        req2 = urllib.request.Request(url_cp, headers={'User-Agent': 'FinanzasHogar/1.2'})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = json.loads(resp2.read())
        cuotapartes = data2.get('data', [])
        if cuotapartes:
            cp    = cuotapartes[0]
            valor = float(cp.get('valor', 0))
            return {
                'precio':    round(valor, 6),
                'variacion': None,
                'moneda':    'ARS',
                'fuente':    f"CAFCI — {fondo_encontrado.get('nombre', '')[:40]}",
            }
    except Exception:
        pass
    return None


def _obtener_precio_activo(asset_name: str, asset_type: str,
                           ticker: str | None) -> dict | None:
    """
    Estrategia de obtención de precio según tipo de activo y ticker disponible.
    Retorna dict con 'precio', 'variacion', 'moneda', 'fuente' o None si no hay datos.
    """
    ticker_limpio = (ticker or '').strip().upper()
    nombre_limpio = asset_name.strip()

    # ── Criptomonedas ─────────────────────────────────────────────────────────
    if asset_type == 'Cripto':
        # Buscar ID de CoinGecko por ticker o nombre
        cg_id = _TICKER_HINTS.get(ticker_limpio.lower()) or \
                _TICKER_HINTS.get(nombre_limpio.lower())
        if cg_id:
            return fetch_precio_coingecko(cg_id)
        # Intentar con el nombre directamente en CoinGecko
        return fetch_precio_coingecko(nombre_limpio.lower())

    # ── FCI ───────────────────────────────────────────────────────────────────
    if asset_type == 'FCI':
        return fetch_precio_fci(nombre_limpio)

    # ── Bonos → BYMA ──────────────────────────────────────────────────────────
    if asset_type == 'Bonos':
        sym = ticker_limpio or nombre_limpio.upper()
        resultado = fetch_precio_byma(sym)
        if resultado:
            return resultado
        # Fallback a Yahoo con sufijo .BA
        if not sym.endswith('.BA'):
            resultado = fetch_precio_yahoo(sym + '.BA')
        return resultado

    # ── Acciones y CEDEARs → Yahoo Finance ────────────────────────────────────
    if asset_type in ('Acciones', 'CEDEAR', 'Otro'):
        sym = ticker_limpio or nombre_limpio.upper()
        # Intentar con el ticker tal cual (puede ser AAPL, GGAL.BA, etc.)
        resultado = fetch_precio_yahoo(sym)
        if resultado:
            return resultado
        # Si no tiene sufijo .BA, intentar agregándolo (acciones argentinas)
        if not sym.endswith('.BA') and asset_type in ('Acciones', 'CEDEAR'):
            return fetch_precio_yahoo(sym + '.BA')
        return None

    return None


def actualizar_precios_mercado(db_path: str, solo_activos: list | None = None) -> dict:
    """
    Actualiza los precios de mercado de todas las posiciones abiertas.
    solo_activos: lista de asset_name a actualizar (None = todos).
    Retorna resumen {'actualizados': N, 'fallidos': [...], 'total': N}
    """
    conn = get_db(db_path)
    cur  = conn.cursor()

    # Obtener posiciones abiertas con ticker
    query = """
        SELECT DISTINCT asset_name, asset_type,
               COALESCE(ticker, '') as ticker
        FROM investments
        WHERE 1=1
    """
    params = []
    if solo_activos:
        placeholders = ','.join(['?'] * len(solo_activos))
        query += f" AND asset_name IN ({placeholders})"
        params = solo_activos

    activos = cur.fetchall() if not params else None
    cur.execute(query, params)
    activos = cur.fetchall()
    conn.close()

    actualizados = 0
    fallidos     = []
    from datetime import datetime

    for row in activos:
        asset_name  = row['asset_name']
        asset_type  = row['asset_type']
        ticker_val  = row['ticker'] or ''

        resultado = _obtener_precio_activo(asset_name, asset_type, ticker_val)

        conn2 = get_db(db_path)
        if resultado and resultado.get('precio'):
            conn2.execute("""
                INSERT INTO precios_mercado
                    (asset_name, ticker, precio_actual, variacion_dia, moneda, fuente, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_name) DO UPDATE SET
                    ticker        = excluded.ticker,
                    precio_actual = excluded.precio_actual,
                    variacion_dia = excluded.variacion_dia,
                    moneda        = excluded.moneda,
                    fuente        = excluded.fuente,
                    updated_at    = excluded.updated_at
            """, (
                asset_name,
                ticker_val or None,
                resultado['precio'],
                resultado.get('variacion'),
                resultado['moneda'],
                resultado.get('fuente'),
                datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            ))
            conn2.commit()
            actualizados += 1
        else:
            fallidos.append(asset_name)
        conn2.close()

    return {
        'actualizados': actualizados,
        'fallidos':     fallidos,
        'total':        len(activos),
    }


def get_investment_summary(db_path: str) -> dict:
    """
    Calcula posición actual de inversiones con precios de mercado, P&L y rendimiento.
    Incluye: posiciones abiertas, ganancia/pérdida por posición, resumen total.
    """
    conn = get_db(db_path)
    cur  = conn.cursor()

    # ── Posiciones abiertas ────────────────────────────────────────────────────
    cur.execute("""
        SELECT i.asset_name, i.asset_type, i.currency,
               COALESCE(i.ticker, '') as ticker,
               SUM(CASE WHEN i.transaction_type='buy'  THEN i.quantity        ELSE -i.quantity        END) as net_qty,
               SUM(CASE WHEN i.transaction_type='buy'  THEN i.quantity*i.price ELSE -i.quantity*i.price END) as costo_total,
               SUM(CASE WHEN i.transaction_type='sell' THEN i.quantity*i.price ELSE 0                  END) as recuperado,
               p.precio_actual, p.variacion_dia, p.moneda as precio_moneda,
               p.fuente as precio_fuente, p.updated_at as precio_fecha
        FROM investments i
        LEFT JOIN precios_mercado p ON p.asset_name = i.asset_name
        GROUP BY i.asset_name, i.asset_type, i.currency
        HAVING net_qty > 0.00001
        ORDER BY i.asset_type, i.asset_name
    """)
    posiciones_raw = [dict(r) for r in cur.fetchall()]

    positions = []
    for p in posiciones_raw:
        qty            = p['net_qty'] or 0
        costo_total    = p['costo_total'] or 0
        costo_promedio = costo_total / qty if qty > 0 else 0
        precio_actual  = p['precio_actual']
        recuperado     = p['recuperado'] or 0

        # Valor a mercado y ganancia/pérdida no realizada
        if precio_actual:
            valor_mercado  = qty * precio_actual
            ganancia_neta  = valor_mercado - costo_total + recuperado
            rendimiento_pct = (ganancia_neta / costo_total * 100) if costo_total else 0
            tiene_precio    = True
        else:
            valor_mercado   = None
            ganancia_neta   = None
            rendimiento_pct = None
            tiene_precio    = False

        p.update({
            'costo_promedio':  round(costo_promedio, 4),
            'valor_mercado':   round(valor_mercado,  2) if valor_mercado  is not None else None,
            'ganancia_neta':   round(ganancia_neta,  2) if ganancia_neta  is not None else None,
            'rendimiento_pct': round(rendimiento_pct, 2) if rendimiento_pct is not None else None,
            'tiene_precio':    tiene_precio,
        })
        positions.append(p)

    # ── Totales por moneda ─────────────────────────────────────────────────────
    cur.execute("""
        SELECT currency,
               SUM(CASE WHEN transaction_type='buy'  THEN quantity*price ELSE 0 END) as total_invertido,
               SUM(CASE WHEN transaction_type='sell' THEN quantity*price ELSE 0 END) as total_recuperado
        FROM investments
        GROUP BY currency
    """)
    totals_raw = {r['currency']: dict(r) for r in cur.fetchall()}

    # Agregar valor a mercado al total
    totals = {}
    for currency, t in totals_raw.items():
        valor_mercado_total = sum(
            p['valor_mercado'] for p in positions
            if p['currency'] == currency and p['valor_mercado'] is not None
        )
        ganancia_total = sum(
            p['ganancia_neta'] for p in positions
            if p['currency'] == currency and p['ganancia_neta'] is not None
        )
        t['valor_mercado_total'] = round(valor_mercado_total, 2)
        t['ganancia_total']      = round(ganancia_total, 2) if ganancia_total else None
        totals[currency] = t

    # ── Historial completo ─────────────────────────────────────────────────────
    cur.execute("""
        SELECT i.*, p.precio_actual, p.updated_at as precio_fecha
        FROM investments i
        LEFT JOIN precios_mercado p ON p.asset_name = i.asset_name
        ORDER BY i.date DESC, i.id DESC
        LIMIT 100
    """)
    history = [dict(r) for r in cur.fetchall()]

    # ── Resumen de precios (para mostrar estado de actualización) ──────────────
    cur.execute("""
        SELECT asset_name, precio_actual, variacion_dia, fuente, updated_at
        FROM precios_mercado
        ORDER BY updated_at DESC
    """)
    precios = {r['asset_name']: dict(r) for r in cur.fetchall()}

    conn.close()
    return {
        'positions': positions,
        'totals':    totals,
        'history':   history,
        'precios':   precios,
    }


# ─── Cotizaciones en tiempo real ───────────────────────────────────────────────

def fetch_all_cotizaciones(db_path: str) -> dict:
    """
    Obtiene cotizaciones actualizadas de múltiples fuentes gratuitas sin API key:
      · dolarapi.com  → todos los tipos de dólar (oficial, blue, MEP, CCL, cripto, tarjeta)
      · frankfurter.app → Euro y otras monedas internacionales
      · api.coingecko.com → Precios de criptomonedas (BTC, ETH, USDT)
    Si alguna fuente falla, se devuelve la caché guardada sin interrumpir la app.
    """
    import urllib.request
    import json
    from datetime import datetime

    resultado = {
        'dolar': [],
        'cripto': [],
        'monedas': [],
        'error_dolar': None,
        'error_cripto': None,
        'error_monedas': None,
        'actualizado_en': None,
        'desde_cache': False,
    }

    # ── 1. Tipos de dólar (dolarapi.com) ──────────────────────────────────────
    try:
        url = "https://dolarapi.com/v1/dolares"
        req = urllib.request.Request(url, headers={'User-Agent': 'FinanzasHogar/1.1'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            datos = json.loads(resp.read())
        nombres_esp = {
            'oficial':   'Oficial',
            'blue':      'Blue (paralelo)',
            'bolsa':     'MEP / Bolsa',
            'contadoconliqui': 'CCL (Conta. c/ Liquidación)',
            'cripto':    'Cripto (USDT)',
            'mayorista': 'Mayorista',
            'tarjeta':   'Tarjeta / Turista',
        }
        for item in datos:
            casa = item.get('casa', '')
            resultado['dolar'].append({
                'nombre':  nombres_esp.get(casa, casa.capitalize()),
                'compra':  item.get('compra'),
                'venta':   item.get('venta'),
                'casa':    casa,
            })
    except Exception as e:
        resultado['error_dolar'] = str(e)

    # ── 2. Euro y monedas internacionales (frankfurter.app — gratuita, sin key) ─
    try:
        url2 = "https://api.frankfurter.app/latest?base=USD&symbols=EUR,BRL,CLP,UYU,GBP"
        req2 = urllib.request.Request(url2, headers={'User-Agent': 'FinanzasHogar/1.1'})
        with urllib.request.urlopen(req2, timeout=6) as resp2:
            datos2 = json.loads(resp2.read())
        nombres_monedas = {
            'EUR': 'Euro',
            'BRL': 'Real brasileño',
            'CLP': 'Peso chileno',
            'UYU': 'Peso uruguayo',
            'GBP': 'Libra esterlina',
        }
        rates = datos2.get('rates', {})
        for codigo, tasa in rates.items():
            resultado['monedas'].append({
                'nombre': nombres_monedas.get(codigo, codigo),
                'codigo': codigo,
                'por_dolar': round(tasa, 4),  # cuántas unidades por 1 USD
            })
    except Exception as e:
        resultado['error_monedas'] = str(e)

    # ── 3. Criptomonedas (CoinGecko — gratuita, sin key) ──────────────────────
    try:
        url3 = ("https://api.coingecko.com/api/v3/simple/price"
                "?ids=bitcoin,ethereum,tether,binancecoin,ripple"
                "&vs_currencies=usd&include_24hr_change=true")
        req3 = urllib.request.Request(url3, headers={'User-Agent': 'FinanzasHogar/1.1'})
        with urllib.request.urlopen(req3, timeout=8) as resp3:
            datos3 = json.loads(resp3.read())
        nombres_cripto = {
            'bitcoin':     ('BTC', 'Bitcoin'),
            'ethereum':    ('ETH', 'Ethereum'),
            'tether':      ('USDT', 'Tether'),
            'binancecoin': ('BNB', 'BNB'),
            'ripple':      ('XRP', 'XRP'),
        }
        for cid, (simbolo, nombre) in nombres_cripto.items():
            if cid in datos3:
                resultado['cripto'].append({
                    'simbolo':  simbolo,
                    'nombre':   nombre,
                    'precio_usd': datos3[cid].get('usd'),
                    'cambio_24h': datos3[cid].get('usd_24h_change'),
                })
    except Exception as e:
        resultado['error_cripto'] = str(e)

    # ── Guardar en caché ───────────────────────────────────────────────────────
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    resultado['actualizado_en'] = ahora

    # Actualizar también la tabla legacy usd_rate para compatibilidad con dashboard
    try:
        oficial = next((d for d in resultado['dolar'] if d['casa'] == 'oficial'), None)
        blue    = next((d for d in resultado['dolar'] if d['casa'] == 'blue'), None)
        conn = get_db(db_path)
        conn.execute("""
            INSERT OR REPLACE INTO usd_rate (id, oficial, blue, updated_at)
            VALUES (1, ?, ?, datetime('now','localtime'))
        """, (
            oficial['venta'] if oficial else None,
            blue['venta']    if blue    else None,
        ))
        conn.execute("""
            INSERT OR REPLACE INTO cotizaciones_cache (id, datos_json, updated_at)
            VALUES (1, ?, datetime('now','localtime'))
        """, (json.dumps(resultado, ensure_ascii=False),))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return resultado


def get_cotizaciones_cache(db_path: str) -> dict | None:
    """Devuelve las últimas cotizaciones guardadas en caché."""
    import json
    try:
        conn = get_db(db_path)
        row = conn.execute(
            "SELECT datos_json, updated_at FROM cotizaciones_cache WHERE id=1"
        ).fetchone()
        conn.close()
        if row and row['datos_json']:
            datos = json.loads(row['datos_json'])
            datos['desde_cache'] = True
            datos['actualizado_en'] = row['updated_at']
            return datos
    except Exception:
        pass
    return None


# ─── Copias de seguridad ───────────────────────────────────────────────────────

def realizar_backup(db_path: str, app_base_dir: str) -> dict:
    """
    Copia la base de datos a la carpeta backups/ con marca de fecha y hora.
    Mantiene solo los últimos N archivos según configuración.
    Retorna {'ok': bool, 'archivo': str, 'mensaje': str}
    """
    import shutil
    from datetime import datetime

    carpeta_backup = os.path.join(app_base_dir, 'backups')
    os.makedirs(carpeta_backup, exist_ok=True)

    # Obtener cantidad máxima de copias desde config
    try:
        conn = get_db(db_path)
        row = conn.execute(
            "SELECT value FROM config WHERE key='backup_cantidad_max'"
        ).fetchone()
        max_copias = int(row['value']) if row else 5
        conn.close()
    except Exception:
        max_copias = 5

    # Nombre del archivo con timestamp
    sello = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f"backup_{sello}.db"
    destino = os.path.join(carpeta_backup, nombre)

    try:
        shutil.copy2(db_path, destino)
    except Exception as e:
        return {'ok': False, 'archivo': '', 'mensaje': f'Error al copiar: {e}'}

    # Registrar fecha de última copia en config
    try:
        conn = get_db(db_path)
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('backup_ultima_vez', ?)",
            (datetime.now().isoformat(),)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Limpiar copias antiguas (mantener solo las últimas N)
    try:
        archivos = sorted([
            f for f in os.listdir(carpeta_backup) if f.startswith('backup_') and f.endswith('.db')
        ])
        while len(archivos) > max_copias:
            os.remove(os.path.join(carpeta_backup, archivos.pop(0)))
    except Exception:
        pass

    return {'ok': True, 'archivo': nombre, 'mensaje': f'Copia creada: {nombre}'}


def verificar_backup_automatico(db_path: str, app_base_dir: str):
    """
    Verifica si corresponde hacer un backup automático según la frecuencia configurada.
    Se llama al iniciar la aplicación. No lanza excepciones.
    """
    from datetime import datetime, timedelta
    try:
        conn = get_db(db_path)
        cur  = conn.cursor()
        cur.execute("SELECT value FROM config WHERE key='backup_frecuencia'")
        row_frec = cur.fetchone()
        cur.execute("SELECT value FROM config WHERE key='backup_ultima_vez'")
        row_ultima = cur.fetchone()
        conn.close()

        frecuencia = row_frec['value'] if row_frec else 'semanal'
        if frecuencia == 'nunca':
            return

        ultima_str = row_ultima['value'] if row_ultima else ''
        ahora = datetime.now()

        if not ultima_str:
            # Nunca se hizo backup → hacer uno ahora
            realizar_backup(db_path, app_base_dir)
            return

        ultima = datetime.fromisoformat(ultima_str)
        deltas = {'diario': 1, 'semanal': 7, 'mensual': 30}
        dias = deltas.get(frecuencia, 7)

        if ahora - ultima >= timedelta(days=dias):
            realizar_backup(db_path, app_base_dir)
    except Exception:
        pass  # Nunca bloquear el arranque por un backup


def listar_backups(app_base_dir: str) -> list:
    """Devuelve lista de archivos de backup ordenados del más reciente al más antiguo."""
    carpeta = os.path.join(app_base_dir, 'backups')
    if not os.path.isdir(carpeta):
        return []
    archivos = []
    for f in sorted(os.listdir(carpeta), reverse=True):
        if f.startswith('backup_') and f.endswith('.db'):
            ruta = os.path.join(carpeta, f)
            tamanio_kb = round(os.path.getsize(ruta) / 1024, 1)
            # Extraer fecha del nombre backup_YYYYMMDD_HHMMSS.db
            try:
                partes = f.replace('backup_','').replace('.db','')
                dt = datetime.strptime(partes, '%Y%m%d_%H%M%S')
                fecha_legible = dt.strftime('%d/%m/%Y %H:%M:%S')
            except Exception:
                fecha_legible = f
            archivos.append({
                'nombre':       f,
                'fecha':        fecha_legible,
                'tamanio_kb':   tamanio_kb,
            })
    return archivos


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS NECESARIO vs PRESCINDIBLE
# ══════════════════════════════════════════════════════════════════════════════

def get_analisis_necesario_prescindible(db_path: str, year: int, month: int) -> dict:
    """
    Calcula el desglose de gastos necesarios vs prescindibles para un mes dado.
    Incluye comparación con el mes anterior y recomendaciones básicas.
    """
    conn = get_db(db_path)

    mes_str  = f"{year}-{month:02d}"
    # Mes anterior
    if month == 1:
        mes_ant_str = f"{year-1}-12"
    else:
        mes_ant_str = f"{year}-{month-1:02d}"

    # ── Totales del mes actual ────────────────────────────────────────────────
    rows = conn.execute("""
        SELECT c.es_necesario,
               c.name        AS categoria,
               SUM(t.amount) AS total
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE t.type = 'expense'
          AND t.currency = 'ARS'
          AND strftime('%Y-%m', t.date) = ?
        GROUP BY c.id, c.es_necesario
        ORDER BY c.es_necesario DESC, total DESC
    """, (mes_str,)).fetchall()

    necesarios    = [dict(r) for r in rows if r['es_necesario'] == 1]
    prescindibles = [dict(r) for r in rows if r['es_necesario'] == 0]

    total_nec  = sum(r['total'] for r in necesarios)
    total_pres = sum(r['total'] for r in prescindibles)
    total_gral = total_nec + total_pres

    # Gastos sin categoría (cuentan como necesarios por defecto)
    sin_cat = conn.execute("""
        SELECT SUM(amount) as total FROM transactions
        WHERE type='expense' AND currency='ARS'
          AND category_id IS NULL
          AND strftime('%Y-%m', date) = ?
    """, (mes_str,)).fetchone()
    total_sin_cat = sin_cat['total'] or 0
    total_nec   += total_sin_cat
    total_gral  += total_sin_cat

    pct_nec  = round(total_nec  / total_gral * 100, 1) if total_gral else 0
    pct_pres = round(total_pres / total_gral * 100, 1) if total_gral else 0

    # ── Totales del mes anterior (para comparar) ──────────────────────────────
    rows_ant = conn.execute("""
        SELECT c.es_necesario, SUM(t.amount) AS total
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE t.type='expense' AND t.currency='ARS'
          AND strftime('%Y-%m', t.date) = ?
        GROUP BY c.es_necesario
    """, (mes_ant_str,)).fetchall()

    total_nec_ant  = sum(r['total'] for r in rows_ant if r['es_necesario'] == 1)
    total_pres_ant = sum(r['total'] for r in rows_ant if r['es_necesario'] == 0)

    # ── Top 3 prescindibles (para recomendaciones) ────────────────────────────
    top_pres = sorted(prescindibles, key=lambda x: x['total'], reverse=True)[:5]

    # ── Variación mes a mes ───────────────────────────────────────────────────
    def variacion(actual, anterior):
        if anterior == 0:
            return None
        return round((actual - anterior) / anterior * 100, 1)

    var_nec  = variacion(total_nec,  total_nec_ant)
    var_pres = variacion(total_pres, total_pres_ant)

    # ── Recomendaciones básicas (sin IA) ─────────────────────────────────────
    recomendaciones = []

    if total_gral > 0:
        if pct_pres > 40:
            recomendaciones.append({
                'tipo': 'alerta',
                'texto': f'El {pct_pres:.0f}% de tus gastos son prescindibles. '
                         f'Revisá si podés reducir alguno para mejorar tu ahorro.'
            })
        elif pct_pres > 25:
            recomendaciones.append({
                'tipo': 'advertencia',
                'texto': f'Un {pct_pres:.0f}% de gastos prescindibles está en un rango moderado. '
                         f'Controlá que no sigan creciendo.'
            })
        else:
            recomendaciones.append({
                'tipo': 'ok',
                'texto': f'Muy bien: solo el {pct_pres:.0f}% de tus gastos son prescindibles. '
                         f'Tus finanzas están bien orientadas.'
            })

    if var_pres is not None and var_pres > 20:
        recomendaciones.append({
            'tipo': 'alerta',
            'texto': f'Los gastos prescindibles subieron un {var_pres:.0f}% respecto al mes anterior.'
        })

    if var_pres is not None and var_pres < -15:
        recomendaciones.append({
            'tipo': 'ok',
            'texto': f'Lograste reducir los gastos prescindibles un {abs(var_pres):.0f}% respecto al mes anterior. ¡Excelente!'
        })

    if top_pres:
        mayor = top_pres[0]
        recomendaciones.append({
            'tipo': 'info',
            'texto': f'Tu mayor gasto prescindible es "{mayor["categoria"]}" con '
                     f'${mayor["total"]:,.0f}. Revisá si podés reducirlo.'
        })

    conn.close()

    return {
        'mes_str':         mes_str,
        'total_necesario': total_nec,
        'total_prescindible': total_pres,
        'total_gral':      total_gral,
        'pct_necesario':   pct_nec,
        'pct_prescindible': pct_pres,
        'necesarios':      necesarios,
        'prescindibles':   prescindibles,
        'top_prescindibles': top_pres,
        # Comparación mes anterior
        'total_nec_anterior':  total_nec_ant,
        'total_pres_anterior': total_pres_ant,
        'variacion_nec':       var_nec,
        'variacion_pres':      var_pres,
        # Recomendaciones
        'recomendaciones': recomendaciones,
    }
