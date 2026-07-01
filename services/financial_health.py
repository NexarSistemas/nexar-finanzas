"""
financial_health.py
Calculo local y defensivo de salud financiera.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from models import get_db


def _default_summary(period: str) -> dict:
    return {
        "score": 0,
        "status": "Critica",
        "period": period,
        "income": 0.0,
        "expenses": 0.0,
        "net_savings": 0.0,
        "savings_rate": 0.0,
        "liquidity": 0.0,
        "alerts": [],
        "components": {
            "currency": "ARS",
            "savings_rate": {"label": "Tasa de ahorro", "score": 0, "value": 0.0, "available": False},
            "liquidity": {"label": "Liquidez", "score": 0, "value": 0.0, "available": False},
            "monthly_balance": {"label": "Balance mensual", "score": 0, "value": 0.0, "available": False},
            "budget_control": {"label": "Control de presupuestos", "score": 0, "value": 0.0, "available": False},
        },
    }


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _status_for_score(score: int) -> str:
    if score <= 39:
        return "Critica"
    if score <= 59:
        return "Inestable"
    if score <= 79:
        return "Buena"
    return "Excelente"


def _pick_primary_currency(conn: sqlite3.Connection, period: str) -> str:
    if _table_exists(conn, "transactions"):
        rows = conn.execute(
            """
            SELECT currency, COUNT(*) AS movement_count, COALESCE(SUM(amount), 0) AS amount_total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY currency
            """,
            (period,),
        ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                row["movement_count"],
                row["amount_total"],
                1 if row["currency"] == "ARS" else 0,
            ),
            reverse=True,
        )
        if ranked:
            return ranked[0]["currency"] or "ARS"

    if _table_exists(conn, "accounts"):
        row = conn.execute(
            """
            SELECT currency, COUNT(*) AS account_count
            FROM accounts
            WHERE active = 1
            GROUP BY currency
            ORDER BY account_count DESC, CASE WHEN currency = 'ARS' THEN 1 ELSE 0 END DESC
            LIMIT 1
            """
        ).fetchone()
        if row:
            return row["currency"] or "ARS"

    return "ARS"


def _get_month_totals(conn: sqlite3.Connection, period: str, currency: str) -> tuple[float, float]:
    if not _table_exists(conn, "transactions"):
        return 0.0, 0.0

    rows = conn.execute(
        """
        SELECT type, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE strftime('%Y-%m', date) = ? AND currency = ?
        GROUP BY type
        """,
        (period, currency),
    ).fetchall()
    totals = {"income": 0.0, "expense": 0.0}
    for row in rows:
        tx_type = row["type"]
        if tx_type in totals:
            totals[tx_type] = float(row["total"] or 0.0)
    return totals["income"], totals["expense"]


def _get_liquidity(conn: sqlite3.Connection, currency: str) -> float:
    if not _table_exists(conn, "accounts"):
        return 0.0

    row = conn.execute(
        """
        SELECT COALESCE(SUM(current_balance), 0) AS total
        FROM accounts
        WHERE active = 1 AND currency = ?
        """,
        (currency,),
    ).fetchone()
    return float(row["total"] or 0.0) if row else 0.0


def _budget_control_unavailable(reason: str | None = None, score: int = 8) -> dict:
    result = {
        "score": score,
        "value": 0.0,
        "available": False,
        "budget_count": 0,
        "over_budget_count": 0,
        "usage_rate": 0.0,
    }
    if reason:
        result["skipped_reason"] = reason
    return result


def _get_budget_control(
    conn: sqlite3.Connection, period: str, year: int, month: int, currency: str
) -> dict:
    # Los presupuestos actuales no guardan moneda y la UI los trata como ARS.
    # Si la moneda principal del periodo es otra, no se comparan montos para evitar
    # puntajes incorrectos por mezclar gastos USD con limites ARS.
    if currency != "ARS":
        return _budget_control_unavailable(
            "El control de presupuestos se omite porque los presupuestos actuales estan expresados en ARS y la moneda principal analizada no es ARS."
        )

    if not (
        _table_exists(conn, "budgets")
        and _table_exists(conn, "transactions")
        and _table_exists(conn, "categories")
    ):
        return _budget_control_unavailable()

    rows = conn.execute(
        """
        SELECT
            b.amount AS budget_amount,
            COALESCE((
                SELECT SUM(t.amount)
                FROM transactions t
                WHERE t.category_id = b.category_id
                  AND t.type = 'expense'
                  AND t.currency = ?
                  AND strftime('%Y-%m', t.date) = ?
            ), 0) AS spent_amount
        FROM budgets b
        WHERE b.year = ? AND b.month = ?
        """,
        (currency, period, year, month),
    ).fetchall()

    if not rows:
        return _budget_control_unavailable()

    over_budget_count = 0
    usage_values = []
    for row in rows:
        budget_amount = float(row["budget_amount"] or 0.0)
        spent_amount = float(row["spent_amount"] or 0.0)
        if budget_amount <= 0:
            continue
        usage_ratio = spent_amount / budget_amount
        usage_values.append(usage_ratio)
        if usage_ratio > 1:
            over_budget_count += 1

    if not usage_values:
        result = _budget_control_unavailable()
        result["budget_count"] = len(rows)
        return result

    average_usage = sum(usage_values) / len(usage_values)
    if over_budget_count == 0 and average_usage <= 0.8:
        score = 15
    else:
        score = _clamp(15 - (over_budget_count * 5) - max(0.0, average_usage - 0.8) * 15, 0, 15)

    return {
        "score": score,
        "value": round(average_usage * 100, 2),
        "available": True,
        "budget_count": len(rows),
        "over_budget_count": over_budget_count,
        "usage_rate": average_usage,
    }


def get_financial_health_summary(db_path: str) -> dict:
    today = date.today()
    period = f"{today.year:04d}-{today.month:02d}"
    summary = _default_summary(period)

    try:
        conn = get_db(db_path)
    except sqlite3.Error:
        summary["alerts"] = ["No se pudo leer la base de datos para calcular la salud financiera."]
        return summary

    try:
        currency = _pick_primary_currency(conn, period)
        income, expenses = _get_month_totals(conn, period, currency)
        net_savings = income - expenses
        liquidity = _get_liquidity(conn, currency)

        savings_rate = (net_savings / income * 100.0) if income > 0 else 0.0
        liquidity_ratio = (liquidity / expenses) if expenses > 0 else (1.0 if liquidity > 0 else 0.0)
        budget_control = _get_budget_control(conn, period, today.year, today.month, currency)

        if savings_rate <= 0:
            savings_score = 0
        elif savings_rate >= 25:
            savings_score = 35
        else:
            savings_score = _clamp((savings_rate / 25.0) * 35.0, 0, 35)

        if liquidity_ratio <= 0:
            liquidity_score = 0
        elif liquidity_ratio >= 1.5:
            liquidity_score = 25
        else:
            liquidity_score = _clamp((liquidity_ratio / 1.5) * 25.0, 0, 25)

        if expenses <= 0 and income <= 0:
            balance_score = 0
        elif net_savings >= 0:
            balance_score = 25
        elif expenses > 0:
            balance_score = _clamp((income / expenses) * 25.0, 0, 25)
        else:
            balance_score = 0

        total_score = savings_score + liquidity_score + balance_score + budget_control["score"]

        alerts = []
        if income == 0 and expenses == 0:
            alerts.append("Todavia no hay movimientos en el periodo actual para calcular tendencias.")
        if income == 0 and expenses > 0:
            alerts.append("No se registran ingresos en la moneda analizada durante este mes.")
        if net_savings < 0:
            alerts.append("Los gastos del mes superan a los ingresos.")
        if income > 0 and savings_rate < 10:
            alerts.append("La tasa de ahorro del mes esta por debajo del 10%.")
        if expenses > 0 and liquidity_ratio < 0.5:
            alerts.append("La liquidez disponible cubre menos de la mitad de los gastos del mes.")
        if liquidity < 0:
            alerts.append("La liquidez disponible es negativa en la moneda principal analizada.")
        if not budget_control["available"]:
            alerts.append(
                budget_control.get(
                    "skipped_reason",
                    "No hay presupuestos cargados para evaluar control basico de gastos.",
                )
            )
        elif budget_control["over_budget_count"] > 0:
            alerts.append(
                f"Hay {budget_control['over_budget_count']} presupuesto(s) del mes por encima del limite."
            )

        score = _clamp(total_score)
        summary.update(
            {
                "score": score,
                "status": _status_for_score(score),
                "income": round(income, 2),
                "expenses": round(expenses, 2),
                "net_savings": round(net_savings, 2),
                "savings_rate": round(savings_rate, 2),
                "liquidity": round(liquidity, 2),
                "alerts": alerts,
                "components": {
                    "currency": currency,
                    "savings_rate": {
                        "label": "Tasa de ahorro",
                        "score": savings_score,
                        "value": round(savings_rate, 2),
                        "available": income > 0,
                    },
                    "liquidity": {
                        "label": "Liquidez",
                        "score": liquidity_score,
                        "value": round(liquidity_ratio, 2),
                        "available": liquidity > 0 or expenses > 0,
                    },
                    "monthly_balance": {
                        "label": "Balance mensual",
                        "score": balance_score,
                        "value": round(net_savings, 2),
                        "available": income > 0 or expenses > 0,
                    },
                    "budget_control": {
                        "label": "Control de presupuestos",
                        "score": budget_control["score"],
                        "value": budget_control["value"],
                        "available": budget_control["available"],
                    },
                },
            }
        )
        return summary
    finally:
        conn.close()
