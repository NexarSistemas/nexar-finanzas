"""
ai_service.py
Módulo de inteligencia artificial para Finanzas del Hogar.

Funcionalidades:
  1. Clasificación automática de gastos/ingresos por descripción
  2. Asistente financiero con acceso a los datos del usuario (chat)

Usa la API de Anthropic (Claude). No requiere conexión si la clave no está configurada:
el sistema degrada graciosamente y funciona sin IA.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime


# ── Constantes ────────────────────────────────────────────────────────────────
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL             = "claude-haiku-4-5-20251001"   # Rápido y económico para tareas simples
TIMEOUT           = 12  # segundos


# ── Llamada base a la API ─────────────────────────────────────────────────────

def _llamar_api(api_key: str, system_prompt: str, messages: list,
                max_tokens: int = 300) -> str | None:
    """
    Realiza una llamada a la API de Anthropic.
    Retorna el texto de la respuesta o None si hay error.
    """
    payload = {
        "model":      MODEL,
        "max_tokens": max_tokens,
        "system":     system_prompt,
        "messages":   messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        ANTHROPIC_API_URL,
        data    = data,
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resultado = json.loads(resp.read().decode("utf-8"))
            return resultado["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", errors="ignore")
        try:
            err = json.loads(cuerpo)
            return f"__ERROR__:{err.get('error', {}).get('message', 'Error API')}"
        except Exception:
            return f"__ERROR__:HTTP {e.code}"
    except urllib.error.URLError:
        return "__ERROR__:Sin conexión a internet"
    except Exception as e:
        return f"__ERROR__:{str(e)[:80]}"


# ── 1. Clasificación automática ───────────────────────────────────────────────

def clasificar_transaccion(api_key: str, descripcion: str,
                           monto: float, tipo: str,
                           categorias: list) -> dict:
    """
    Sugiere la categoría más apropiada para una transacción.

    Args:
        api_key:     Clave de API de Anthropic
        descripcion: Texto libre ingresado por el usuario
        monto:       Monto de la transacción
        tipo:        'expense' o 'income'
        categorias:  Lista de dicts {id, name, type} disponibles en el sistema

    Returns:
        {
          'category_id':   int o None,
          'category_name': str o None,
          'confianza':     'alta' | 'media' | 'baja',
          'razon':         str (breve explicación),
          'error':         str o None
        }
    """
    tipo_es = "gasto" if tipo == "expense" else "ingreso"
    cats_filtradas = [c for c in categorias if c["type"] == tipo]

    if not cats_filtradas:
        return {"category_id": None, "category_name": None,
                "confianza": "baja", "razon": "Sin categorías disponibles", "error": None}

    lista_cats = "\n".join(f'- ID {c["id"]}: {c["name"]}' for c in cats_filtradas)

    system = (
        "Sos un asistente de finanzas personales para Argentina. "
        "Tu única tarea es clasificar transacciones en una categoría. "
        "Respondé SIEMPRE con un JSON válido, sin texto adicional, sin markdown."
    )

    user_msg = f"""Clasificá esta transacción:

Tipo: {tipo_es}
Descripción: "{descripcion}"
Monto: ${monto:,.2f} ARS

Categorías disponibles:
{lista_cats}

Respondé con este JSON exacto:
{{
  "category_id": <número entero del ID más adecuado>,
  "category_name": "<nombre de la categoría>",
  "confianza": "<alta|media|baja>",
  "razon": "<una frase breve explicando por qué>"
}}

Si ninguna categoría es adecuada, usá category_id: null."""

    respuesta = _llamar_api(api_key, system, [{"role": "user", "content": user_msg}],
                            max_tokens=150)

    if not respuesta:
        return {"category_id": None, "category_name": None,
                "confianza": "baja", "razon": "Sin respuesta", "error": "Sin respuesta"}

    if respuesta.startswith("__ERROR__:"):
        return {"category_id": None, "category_name": None,
                "confianza": "baja", "razon": "", "error": respuesta[10:]}

    try:
        # Limpiar posibles backticks de markdown
        texto = respuesta.strip().strip("`").strip()
        if texto.startswith("json"):
            texto = texto[4:].strip()
        resultado = json.loads(texto)
        # Validar que el ID existe en las categorías disponibles
        ids_validos = {c["id"] for c in cats_filtradas}
        cat_id = resultado.get("category_id")
        if cat_id and cat_id not in ids_validos:
            resultado["category_id"]   = None
            resultado["category_name"] = None
            resultado["confianza"]     = "baja"
        resultado["error"] = None
        return resultado
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"category_id": None, "category_name": None,
                "confianza": "baja", "razon": "No se pudo interpretar la respuesta",
                "error": "parse_error"}


# ── 2. Asistente financiero ───────────────────────────────────────────────────

def construir_contexto_financiero(db_path: str) -> str:
    """
    Arma un resumen del estado financiero del usuario para enviarlo como contexto al asistente.
    No envía datos sensibles (contraseñas, claves). Solo números y categorías.
    """
    try:
        from models import get_db
        from datetime import date

        conn = get_db(db_path)
        cur  = conn.cursor()
        hoy  = date.today()

        # Mes actual
        mes   = hoy.month
        anio  = hoy.year
        mes_str = f"{anio}-{mes:02d}"

        # Saldo por cuenta
        cuentas = cur.execute("""
            SELECT a.name, a.type, a.currency,
                   COALESCE(SUM(CASE WHEN t.type='income' THEN t.amount
                                     WHEN t.type='expense' THEN -t.amount ELSE 0 END), 0) as saldo
            FROM accounts a
            LEFT JOIN transactions t ON t.account_id = a.id
            GROUP BY a.id
        """).fetchall()

        ctx_cuentas = ""
        for c in cuentas:
            ctx_cuentas += f"  - {c['name']} ({c['type']}, {c['currency']}): ${c['saldo']:,.2f}\n"

        # Transacciones del mes actual
        txs = cur.execute("""
            SELECT t.type, t.amount, t.currency, t.date, t.description,
                   COALESCE(c.name, 'Sin categoría') as categoria
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE strftime('%Y-%m', t.date) = ?
            ORDER BY t.date DESC
            LIMIT 50
        """, (mes_str,)).fetchall()

        total_ingresos = sum(t["amount"] for t in txs if t["type"] == "income")
        total_gastos   = sum(t["amount"] for t in txs if t["type"] == "expense")

        # Gastos por categoría este mes
        cats_gasto = cur.execute("""
            SELECT COALESCE(c.name,'Sin categoría') as cat,
                   SUM(t.amount) as total
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.type='expense' AND strftime('%Y-%m', t.date) = ?
            GROUP BY cat ORDER BY total DESC LIMIT 8
        """, (mes_str,)).fetchall()

        ctx_cats = ""
        for cg in cats_gasto:
            ctx_cats += f"  - {cg['cat']}: ${cg['total']:,.2f}\n"

        # Presupuestos del mes
        presupuestos = cur.execute("""
            SELECT b.category_name, b.amount as limite,
                   COALESCE(SUM(t.amount), 0) as gastado
            FROM budgets b
            LEFT JOIN transactions t ON t.category_id = b.category_id
                AND strftime('%Y-%m', t.date) = ?
                AND t.type = 'expense'
            WHERE b.month = ? OR b.month IS NULL
            GROUP BY b.id
        """, (mes_str, mes_str)).fetchall()

        ctx_presup = ""
        for p in presupuestos:
            pct = (p["gastado"] / p["limite"] * 100) if p["limite"] else 0
            ctx_presup += f"  - {p['category_name']}: ${p['gastado']:,.2f} / ${p['limite']:,.2f} ({pct:.0f}%)\n"

        # Inversiones abiertas
        inversiones = cur.execute("""
            SELECT asset_name, asset_type, currency,
                   SUM(CASE WHEN transaction_type='buy' THEN quantity ELSE -quantity END) as qty,
                   SUM(CASE WHEN transaction_type='buy' THEN quantity*price ELSE -quantity*price END) as costo
            FROM investments
            GROUP BY asset_name HAVING qty > 0.0001
        """).fetchall()

        ctx_inv = ""
        for inv in inversiones:
            ctx_inv += f"  - {inv['asset_name']} ({inv['asset_type']}): {inv['qty']:.4f} uds, costo ${inv['costo']:,.2f} {inv['currency']}\n"

        # Últimas 10 transacciones del mes
        ctx_ultimas = ""
        for t in txs[:10]:
            signo = "+" if t["type"] == "income" else "-"
            ctx_ultimas += f"  [{t['date']}] {signo}${t['amount']:,.2f} {t['categoria']} — {t['description'] or ''}\n"

        conn.close()

        return f"""=== ESTADO FINANCIERO DEL USUARIO ===
Fecha: {hoy.strftime('%d/%m/%Y')} | Mes analizado: {mes:02d}/{anio}

CUENTAS Y SALDOS:
{ctx_cuentas or '  (Sin cuentas registradas)'}

RESUMEN DEL MES:
  Ingresos totales:  ${total_ingresos:,.2f}
  Gastos totales:    ${total_gastos:,.2f}
  Balance del mes:   ${total_ingresos - total_gastos:,.2f}

GASTOS POR CATEGORÍA (mes actual):
{ctx_cats or '  (Sin gastos registrados)'}

PRESUPUESTOS:
{ctx_presup or '  (Sin presupuestos configurados)'}

INVERSIONES ABIERTAS:
{ctx_inv or '  (Sin inversiones registradas)'}

ÚLTIMAS TRANSACCIONES:
{ctx_ultimas or '  (Sin transacciones)'}
====================================="""

    except Exception as e:
        return f"=== Error al obtener datos financieros: {str(e)[:100]} ==="


def chat_asistente(api_key: str, mensaje: str, historial: list,
                   contexto_financiero: str) -> dict:
    """
    Responde una pregunta del usuario sobre sus finanzas.

    Args:
        api_key:              Clave de API de Anthropic
        mensaje:              Pregunta del usuario
        historial:            Lista de {role, content} de mensajes previos (máx 10)
        contexto_financiero:  String con el estado financiero del usuario

    Returns:
        {
          'respuesta': str,
          'error':     str o None
        }
    """
    system = f"""Sos un asistente financiero personal amigable y conciso para Argentina.
Tenés acceso a los datos financieros reales del usuario. Respondé siempre en español rioplatense (vos, etc).
Sé directo, útil y humano. Usá números del contexto cuando sea relevante.
No inventes datos que no estén en el contexto. Si algo no está en los datos, decilo.
No des consejos de inversión específicos ("comprá X"). Podés analizar lo que ya tiene.
Respondé de forma concisa (máximo 3-4 párrafos). Usá emojis con moderación.

{contexto_financiero}"""

    # Limitar historial a los últimos 10 mensajes para no exceder tokens
    msgs = historial[-10:] + [{"role": "user", "content": mensaje}]

    respuesta = _llamar_api(api_key, system, msgs, max_tokens=600)

    if not respuesta:
        return {"respuesta": None, "error": "Sin respuesta del servidor"}

    if respuesta.startswith("__ERROR__:"):
        error_msg = respuesta[10:]
        if "401" in error_msg or "invalid" in error_msg.lower() or "auth" in error_msg.lower():
            return {"respuesta": None,
                    "error": "Clave de API inválida. Verificala en Configuración → Inteligencia Artificial."}
        if "Sin conexión" in error_msg:
            return {"respuesta": None,
                    "error": "Sin conexión a internet. El asistente requiere conexión para funcionar."}
        return {"respuesta": None, "error": error_msg}

    return {"respuesta": respuesta, "error": None}
