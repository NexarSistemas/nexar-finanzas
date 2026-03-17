"""
routes.py
Todas las rutas (endpoints) de la aplicación Flask.
Maneja autenticación, transacciones, cuentas, presupuestos, inversiones y reportes.
"""

import os
import sys
import hashlib
import io
from datetime import date, datetime
from functools import wraps
from flask import (
    render_template, redirect, url_for, request, session,
    flash, g, current_app, send_file, make_response, jsonify
)

from models import get_db, recalculate_account_balance
from demo_limits import check_limit, is_full_version, get_demo_status
from activation import validate_activation_code
from licensing.hardware_id import get_hardware_id
import services


# ─── Utilidades ───────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def login_required(f):
    """Decorador: redirige al login si no hay sesión activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debés iniciar sesión para acceder.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_db_path():
    return current_app.config['DB_PATH']


def register_routes(app):
    """Registra todas las rutas en la instancia Flask."""

    # ══════════════════════════════════════════════════════════════════════════
    # AUTH
    # ══════════════════════════════════════════════════════════════════════════

    def _user_exists() -> bool:
        """Verifica si ya existe al menos un usuario en la base de datos."""
        try:
            db = get_db(get_db_path())
            row = db.execute("SELECT id FROM user LIMIT 1").fetchone()
            db.close()
            return row is not None
        except Exception:
            return False

    @app.route('/')
    def index():
        # Si no hay ningún usuario creado, ir a la configuración inicial
        if not _user_exists():
            return redirect(url_for('setup'))
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # Redirigir al setup si no existe ningún usuario todavía
        if not _user_exists():
            return redirect(url_for('setup'))
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            db = get_db(get_db_path())
            user = db.execute(
                "SELECT * FROM user WHERE username = ?", (username,)
            ).fetchone()
            db.close()

            if user and user['password_hash'] == hash_password(password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session.permanent = False
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')

        return render_template('login.html')

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        """Primera configuración: crear usuario administrador."""
        # Si ya existe un usuario, no permitir volver al setup
        if _user_exists():
            return redirect(url_for('login'))

        if request.method == 'POST':
            username  = request.form.get('username', 'admin').strip() or 'admin'
            password  = request.form.get('password', '')
            confirm   = request.form.get('confirm', '')
            rec_q     = request.form.get('recovery_question', '').strip()
            rec_a     = request.form.get('recovery_answer', '').strip().lower()

            if len(password) < 4:
                flash('La contraseña debe tener al menos 4 caracteres.', 'danger')
            elif password != confirm:
                flash('Las contraseñas no coinciden.', 'danger')
            elif not rec_q:
                flash('Escribí una pregunta de seguridad.', 'danger')
            elif len(rec_a) < 2:
                flash('La respuesta de seguridad debe tener al menos 2 caracteres.', 'danger')
            else:
                db = get_db(get_db_path())
                db.execute(
                    "INSERT INTO user (id, username, password_hash, recovery_question, recovery_answer_hash) VALUES (1, ?, ?, ?, ?)",
                    (username, hash_password(password), rec_q, hash_password(rec_a))
                )
                db.commit()
                db.close()
                flash(f'¡Bienvenido/a {username}! Iniciá sesión con tu nueva contraseña.', 'success')
                return redirect(url_for('login'))

        return render_template('setup.html')

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Paso 1 — verificar respuesta secreta. Paso 2 — ingresar nueva contraseña."""
        if not _user_exists():
            return redirect(url_for('setup'))
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        db       = get_db(get_db_path())
        user     = db.execute("SELECT * FROM user WHERE id=1").fetchone()
        db.close()

        # Si no tiene pregunta configurada no podemos recuperar
        if not user or not user['recovery_question']:
            flash('No hay pregunta de seguridad configurada. Contactá al administrador.', 'warning')
            return redirect(url_for('login'))

        step = request.args.get('step', '1')

        if request.method == 'POST':
            action = request.form.get('action')

            # ── Paso 1: verificar respuesta ──────────────────────────────────
            if action == 'verify_answer':
                answer = request.form.get('recovery_answer', '').strip().lower()
                if user['recovery_answer_hash'] == hash_password(answer):
                    # Guardar token temporal en sesión Flask (sin BD)
                    session['recovery_verified'] = True
                    session['recovery_user_id']  = user['id']
                    return redirect(url_for('forgot_password', step='2'))
                else:
                    flash('Respuesta incorrecta. Intentá nuevamente.', 'danger')
                    return render_template('forgot_password.html',
                                           step='1',
                                           question=user['recovery_question'])

            # ── Paso 2: cambiar contraseña ───────────────────────────────────
            if action == 'reset_password':
                if not session.get('recovery_verified') or session.get('recovery_user_id') != user['id']:
                    flash('Sesión de recuperación inválida. Empezá de nuevo.', 'danger')
                    return redirect(url_for('forgot_password'))

                new_pw  = request.form.get('new_password', '')
                confirm = request.form.get('confirm_password', '')

                if len(new_pw) < 4:
                    flash('La contraseña debe tener al menos 4 caracteres.', 'danger')
                    return render_template('forgot_password.html', step='2')
                if new_pw != confirm:
                    flash('Las contraseñas no coinciden.', 'danger')
                    return render_template('forgot_password.html', step='2')

                db = get_db(get_db_path())
                db.execute("UPDATE user SET password_hash=? WHERE id=1", (hash_password(new_pw),))
                db.commit()
                db.close()

                # Limpiar token de recuperación
                session.pop('recovery_verified', None)
                session.pop('recovery_user_id', None)

                flash('✅ Contraseña restablecida correctamente. Ya podés iniciar sesión.', 'success')
                return redirect(url_for('login'))

        return render_template('forgot_password.html',
                               step=step,
                               question=user['recovery_question'])

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Sesión cerrada correctamente.', 'info')
        return redirect(url_for('login'))

    @app.route('/shutdown')
    def shutdown():
        """Cierre controlado del servidor (accesible desde login y desde sesión activa)."""
        return render_template('shutdown.html')

    @app.route('/shutdown/confirm', methods=['POST'])
    def shutdown_confirm():
        """Cierre controlado del servidor.
        No requiere @login_required: el usuario puede cerrar la app desde
        el login (después de cerrar sesión) sin quedar con ventana en blanco.
        No hay riesgo de seguridad: la única acción es detener la app local.
        """
        import threading, platform

        session.clear()
        sistema = platform.system()

        response = make_response(render_template('shutdown_done.html',
                                                 sistema=sistema))

        def stop():
            import time
            time.sleep(1.5)  # Dar tiempo a que el navegador/webview reciba la respuesta

            # ── Cerrar ventana pywebview si está activa ───────────────────────
            # IMPORTANTE: destruir la ventana ANTES del os._exit para que
            # pywebview no quede colgado con una ventana en blanco.
            # NO matar el proceso padre (puede ser el gestor de sesión en Linux).
            try:
                webview_window = current_app.config.get('WEBVIEW_WINDOW')
                if webview_window is not None:
                    webview_window.destroy()
            except Exception:
                pass

            # ── Terminar el proceso de la app limpiamente ─────────────────────
            os._exit(0)

        threading.Thread(target=stop, daemon=True).start()
        return response

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/dashboard')
    @login_required
    def dashboard():
        data = services.get_dashboard_data(get_db_path())
        today = date.today()
        budget_status = services.get_budget_status(get_db_path(), today.year, today.month)
        return render_template('dashboard.html', data=data, budget_status=budget_status,
                               today=today)

    # ══════════════════════════════════════════════════════════════════════════
    # CUENTAS
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/accounts')
    @login_required
    def accounts():
        db = get_db(get_db_path())
        accs = db.execute(
            "SELECT * FROM accounts WHERE active=1 ORDER BY type, name"
        ).fetchall()
        db.close()
        return render_template('accounts.html', accounts=accs)

    @app.route('/accounts/new', methods=['GET', 'POST'])
    @login_required
    def account_new():
        db = get_db(get_db_path())
        if request.method == 'POST':
            acc_type = request.form.get('type', 'bank')
            # Verificar límites DEMO
            resource = 'bank_accounts' if acc_type == 'bank' else \
                       'virtual_wallets' if acc_type == 'virtual_wallet' else None
            if resource:
                count = db.execute(
                    "SELECT COUNT(*) as n FROM accounts WHERE type=? AND active=1",
                    (acc_type,)
                ).fetchone()['n']
                check = check_limit(get_db_path(), resource, count)
                if not check['allowed']:
                    db.close()
                    flash(check['message'], 'danger')
                    return redirect(url_for('accounts'))

            name            = request.form.get('name', '').strip()
            currency        = request.form.get('currency', 'ARS')
            initial_balance = float(request.form.get('initial_balance', 0) or 0)
            cbu_cvu         = request.form.get('cbu_cvu', '').strip()
            alias           = request.form.get('alias', '').strip()

            if not name:
                flash('El nombre es obligatorio.', 'danger')
            else:
                db.execute("""
                    INSERT INTO accounts (name, type, currency, initial_balance, current_balance, cbu_cvu, alias)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, acc_type, currency, initial_balance, initial_balance, cbu_cvu, alias))
                db.commit()
                flash(f'Cuenta "{name}" creada correctamente.', 'success')
                db.close()
                return redirect(url_for('accounts'))

        db.close()
        return render_template('account_form.html', account=None, action='Crear')

    @app.route('/accounts/<int:acc_id>/edit', methods=['GET', 'POST'])
    @login_required
    def account_edit(acc_id):
        db = get_db(get_db_path())
        account = db.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
        if not account:
            db.close()
            flash('Cuenta no encontrada.', 'danger')
            return redirect(url_for('accounts'))

        if request.method == 'POST':
            name     = request.form.get('name', '').strip()
            currency = request.form.get('currency', 'ARS')
            cbu_cvu  = request.form.get('cbu_cvu', '').strip()
            alias    = request.form.get('alias', '').strip()
            if not name:
                flash('El nombre es obligatorio.', 'danger')
            else:
                db.execute("""
                    UPDATE accounts SET name=?, currency=?, cbu_cvu=?, alias=?
                    WHERE id=?
                """, (name, currency, cbu_cvu, alias, acc_id))
                recalculate_account_balance(db, acc_id)
                db.commit()
                flash('Cuenta actualizada.', 'success')
                db.close()
                return redirect(url_for('accounts'))

        db.close()
        return render_template('account_form.html', account=dict(account), action='Editar')

    @app.route('/accounts/<int:acc_id>/delete', methods=['POST'])
    @login_required
    def account_delete(acc_id):
        db = get_db(get_db_path())
        db.execute("UPDATE accounts SET active=0 WHERE id=?", (acc_id,))
        db.commit()
        db.close()
        flash('Cuenta desactivada correctamente.', 'info')
        return redirect(url_for('accounts'))

    @app.route('/transfers', methods=['GET', 'POST'])
    @login_required
    def transfer():
        db = get_db(get_db_path())
        accounts_list = db.execute(
            "SELECT * FROM accounts WHERE active=1 ORDER BY name"
        ).fetchall()

        if request.method == 'POST':
            from_id  = int(request.form.get('from_account_id', 0))
            to_id    = int(request.form.get('to_account_id', 0))
            amount   = float(request.form.get('amount', 0) or 0)
            currency = request.form.get('currency', 'ARS')
            tx_date  = request.form.get('date', date.today().isoformat())
            desc     = request.form.get('description', '').strip()

            if from_id == to_id:
                flash('Las cuentas de origen y destino deben ser diferentes.', 'danger')
            elif amount <= 0:
                flash('El monto debe ser mayor a cero.', 'danger')
            else:
                db.execute("""
                    INSERT INTO transfers (from_account_id, to_account_id, amount, currency, date, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (from_id, to_id, amount, currency, tx_date, desc))
                recalculate_account_balance(db, from_id)
                recalculate_account_balance(db, to_id)
                db.commit()
                flash('Transferencia registrada correctamente.', 'success')
                db.close()
                return redirect(url_for('accounts'))

        db.close()
        return render_template('transfer_form.html', accounts=accounts_list,
                               today=date.today().isoformat())

    # ══════════════════════════════════════════════════════════════════════════
    # TRANSACCIONES (INGRESOS Y GASTOS)
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/transactions')
    @login_required
    def transactions():
        db = get_db(get_db_path())
        page  = int(request.args.get('page', 1))
        limit = 20
        offset = (page - 1) * limit

        # Filtros
        tx_type  = request.args.get('type', '')
        cat_id   = request.args.get('category', '')
        month    = request.args.get('month', '')
        currency = request.args.get('currency', '')

        where_clauses = []
        params = []
        if tx_type:
            where_clauses.append("t.type = ?")
            params.append(tx_type)
        if cat_id:
            where_clauses.append("t.category_id = ?")
            params.append(cat_id)
        if month:
            where_clauses.append("strftime('%Y-%m', t.date) = ?")
            params.append(month)
        if currency:
            where_clauses.append("t.currency = ?")
            params.append(currency)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = db.execute(
            f"SELECT COUNT(*) as n FROM transactions t {where_sql}", params
        ).fetchone()['n']

        txs = db.execute(f"""
            SELECT t.*, c.name as category_name, a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_id = a.id
            {where_sql}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        categories = db.execute(
            "SELECT * FROM categories WHERE active=1 ORDER BY type, name"
        ).fetchall()
        db.close()

        total_pages = (total + limit - 1) // limit
        return render_template('transactions.html',
                               transactions=txs,
                               categories=categories,
                               page=page, total_pages=total_pages,
                               filters={'type': tx_type, 'category': cat_id,
                                        'month': month, 'currency': currency})

    @app.route('/transactions/new', methods=['GET', 'POST'])
    @login_required
    def transaction_new():
        db = get_db(get_db_path())

        if request.method == 'POST':
            tx_type  = request.form.get('type', 'expense')
            amount   = float(request.form.get('amount', 0) or 0)
            currency = request.form.get('currency', 'ARS')
            cat_id   = request.form.get('category_id') or None
            acc_id   = request.form.get('account_id') or None
            method   = request.form.get('method', 'cash')
            tx_date  = request.form.get('date', date.today().isoformat())
            desc     = request.form.get('description', '').strip()

            # Verificar límites DEMO
            resource = 'expenses' if tx_type == 'expense' else 'incomes'
            count = db.execute(
                "SELECT COUNT(*) as n FROM transactions WHERE type=?", (tx_type,)
            ).fetchone()['n']
            check = check_limit(get_db_path(), resource, count)
            if not check['allowed']:
                db.close()
                flash(check['message'], 'danger')
                return redirect(url_for('transactions'))

            if amount <= 0:
                flash('El monto debe ser mayor a cero.', 'danger')
            else:
                db.execute("""
                    INSERT INTO transactions
                    (type, amount, currency, category_id, account_id, method, date, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (tx_type, amount, currency, cat_id, acc_id, method, tx_date, desc))
                if acc_id:
                    recalculate_account_balance(db, int(acc_id))
                db.commit()
                flash('Movimiento registrado correctamente.', 'success')
                db.close()
                return redirect(url_for('transactions'))

        categories = db.execute(
            "SELECT * FROM categories WHERE active=1 ORDER BY type, name"
        ).fetchall()
        accounts_list = db.execute(
            "SELECT * FROM accounts WHERE active=1 ORDER BY name"
        ).fetchall()
        db.close()
        tx_type_default = request.args.get('type', 'expense')
        return render_template('transaction_form.html',
                               transaction=None,
                               categories=categories,
                               accounts=accounts_list,
                               action='Registrar',
                               today=date.today().isoformat(),
                               tx_type_default=tx_type_default)

    @app.route('/transactions/<int:tx_id>/edit', methods=['GET', 'POST'])
    @login_required
    def transaction_edit(tx_id):
        db = get_db(get_db_path())
        tx = db.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not tx:
            db.close()
            flash('Movimiento no encontrado.', 'danger')
            return redirect(url_for('transactions'))

        old_account_id = tx['account_id']

        if request.method == 'POST':
            amount   = float(request.form.get('amount', 0) or 0)
            currency = request.form.get('currency', 'ARS')
            cat_id   = request.form.get('category_id') or None
            acc_id   = request.form.get('account_id') or None
            method   = request.form.get('method', 'cash')
            tx_date  = request.form.get('date', date.today().isoformat())
            desc     = request.form.get('description', '').strip()

            if amount <= 0:
                flash('El monto debe ser mayor a cero.', 'danger')
            else:
                db.execute("""
                    UPDATE transactions
                    SET amount=?, currency=?, category_id=?, account_id=?,
                        method=?, date=?, description=?
                    WHERE id=?
                """, (amount, currency, cat_id, acc_id, method, tx_date, desc, tx_id))
                if old_account_id:
                    recalculate_account_balance(db, old_account_id)
                if acc_id:
                    recalculate_account_balance(db, int(acc_id))
                db.commit()
                flash('Movimiento actualizado.', 'success')
                db.close()
                return redirect(url_for('transactions'))

        categories = db.execute(
            "SELECT * FROM categories WHERE active=1 ORDER BY type, name"
        ).fetchall()
        accounts_list = db.execute(
            "SELECT * FROM accounts WHERE active=1 ORDER BY name"
        ).fetchall()
        db.close()
        return render_template('transaction_form.html',
                               transaction=dict(tx),
                               categories=categories,
                               accounts=accounts_list,
                               action='Editar',
                               today=date.today().isoformat(),
                               tx_type_default=tx['type'])

    @app.route('/transactions/<int:tx_id>/delete', methods=['POST'])
    @login_required
    def transaction_delete(tx_id):
        db = get_db(get_db_path())
        tx = db.execute("SELECT account_id FROM transactions WHERE id=?", (tx_id,)).fetchone()
        db.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        if tx and tx['account_id']:
            recalculate_account_balance(db, tx['account_id'])
        db.commit()
        db.close()
        flash('Movimiento eliminado.', 'info')
        return redirect(url_for('transactions'))

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORÍAS
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/categories')
    @login_required
    def categories():
        db = get_db(get_db_path())
        cats = db.execute(
            "SELECT * FROM categories WHERE active=1 ORDER BY type, name"
        ).fetchall()
        db.close()
        return render_template('categories.html', categories=cats)

    @app.route('/categories/new', methods=['POST'])
    @login_required
    def category_new():
        name         = request.form.get('name', '').strip()
        cat_type     = request.form.get('type', 'expense')
        es_necesario = int(request.form.get('es_necesario', 1))
        if name:
            db = get_db(get_db_path())
            try:
                db.execute(
                    "INSERT INTO categories (name, type, es_necesario) VALUES (?,?,?)",
                    (name, cat_type, es_necesario)
                )
                db.commit()
                tipo_str = "necesario" if es_necesario else "prescindible"
                flash(f'Categoría "{name}" creada ({tipo_str}).', 'success')
            except Exception:
                flash(f'La categoría "{name}" ya existe.', 'warning')
            db.close()
        return redirect(url_for('categories'))

    @app.route('/categories/<int:cat_id>/toggle-necesario', methods=['POST'])
    @login_required
    def category_toggle_necesario(cat_id):
        """Alterna entre necesario / prescindible para una categoría de gasto."""
        db  = get_db(get_db_path())
        cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        if cat:
            nuevo = 0 if cat['es_necesario'] else 1
            db.execute("UPDATE categories SET es_necesario=? WHERE id=?", (nuevo, cat_id))
            db.commit()
        db.close()
        return redirect(url_for('categories'))

    @app.route('/categories/<int:cat_id>/delete', methods=['POST'])
    @login_required
    def category_delete(cat_id):
        db = get_db(get_db_path())
        db.execute("UPDATE categories SET active=0 WHERE id=?", (cat_id,))
        db.commit()
        db.close()
        flash('Categoría eliminada.', 'info')
        return redirect(url_for('categories'))

    # ══════════════════════════════════════════════════════════════════════════
    # PRESUPUESTOS
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/budgets')
    @login_required
    def budgets():
        today = date.today()
        year  = int(request.args.get('year',  today.year))
        month = int(request.args.get('month', today.month))

        db = get_db(get_db_path())
        budget_list = db.execute("""
            SELECT b.*, c.name as category_name
            FROM budgets b JOIN categories c ON b.category_id = c.id
            WHERE b.year=? AND b.month=?
            ORDER BY c.name
        """, (year, month)).fetchall()

        expense_cats = db.execute(
            "SELECT * FROM categories WHERE type='expense' AND active=1 ORDER BY name"
        ).fetchall()
        db.close()

        status = services.get_budget_status(get_db_path(), year, month)

        return render_template('budgets.html',
                               budgets=budget_list,
                               status=status,
                               expense_cats=expense_cats,
                               year=year, month=month,
                               today=today)

    @app.route('/budgets/save', methods=['POST'])
    @login_required
    def budget_save():
        cat_id = int(request.form.get('category_id', 0))
        amount = float(request.form.get('amount', 0) or 0)
        month  = int(request.form.get('month', date.today().month))
        year   = int(request.form.get('year',  date.today().year))

        if cat_id and amount > 0:
            db = get_db(get_db_path())
            db.execute("""
                INSERT INTO budgets (category_id, amount, month, year)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category_id, month, year) DO UPDATE SET amount=excluded.amount
            """, (cat_id, amount, month, year))
            db.commit()
            db.close()
            flash('Presupuesto guardado.', 'success')
        return redirect(url_for('budgets', year=year, month=month))

    @app.route('/budgets/<int:budget_id>/delete', methods=['POST'])
    @login_required
    def budget_delete(budget_id):
        db = get_db(get_db_path())
        b = db.execute("SELECT year, month FROM budgets WHERE id=?", (budget_id,)).fetchone()
        db.execute("DELETE FROM budgets WHERE id=?", (budget_id,))
        db.commit()
        db.close()
        flash('Presupuesto eliminado.', 'info')
        return redirect(url_for('budgets', year=b['year'] if b else date.today().year,
                                month=b['month'] if b else date.today().month))

    # ══════════════════════════════════════════════════════════════════════════
    # REPORTES
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/reports')
    @login_required
    def reports():
        today = date.today()
        year  = int(request.args.get('year',  today.year))
        month = int(request.args.get('month', today.month))
        mode  = request.args.get('mode', 'monthly')

        if mode == 'annual':
            data = {'annual': services.get_annual_summary(get_db_path(), year)}
        elif mode == 'weekly':
            data = {'weekly': services.get_weekly_summary(get_db_path())}
        else:
            data = {'monthly': services.get_monthly_summary(get_db_path(), year, month)}

        analisis = services.get_analisis_necesario_prescindible(
            get_db_path(), year, month
        ) if mode == 'monthly' else None

        return render_template('reports.html',
                               data=data, mode=mode,
                               year=year, month=month, today=today,
                               analisis=analisis)

    @app.route('/reports/chart/monthly.json')
    @login_required
    def chart_monthly():
        today = date.today()
        year  = int(request.args.get('year',  today.year))
        month = int(request.args.get('month', today.month))
        return jsonify(services.get_monthly_chart_data(get_db_path(), year, month))

    @app.route('/reports/chart/annual.json')
    @login_required
    def chart_annual():
        year = int(request.args.get('year', date.today().year))
        return jsonify(services.get_annual_chart_data(get_db_path(), year))

    @app.route('/reports/export/csv')
    @login_required
    def export_csv():
        today = date.today()
        year  = request.args.get('year')
        month = request.args.get('month')
        year  = int(year)  if year  else None
        month = int(month) if month else None

        content  = services.export_transactions_csv(get_db_path(), year, month)
        filename = f"finanzas_{year or 'todo'}_{month or 'todo'}.csv"
        response = make_response(content)
        response.headers['Content-Type']        = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    # ══════════════════════════════════════════════════════════════════════════
    # INVERSIONES
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/investments')
    @login_required
    def investments():
        data = services.get_investment_summary(get_db_path())
        return render_template('investments.html', data=data)

    @app.route('/investments/new', methods=['GET', 'POST'])
    @login_required
    def investment_new():
        db = get_db(get_db_path())
        if request.method == 'POST':
            # Verificar límites DEMO
            count = db.execute("SELECT COUNT(*) as n FROM investments").fetchone()['n']
            check = check_limit(get_db_path(), 'investments', count)
            if not check['allowed']:
                db.close()
                flash(check['message'], 'danger')
                return redirect(url_for('investments'))

            asset_type = request.form.get('asset_type', 'stock')
            asset_name = request.form.get('asset_name', '').strip()
            ticker     = request.form.get('ticker', '').strip().upper() or None
            tx_type    = request.form.get('transaction_type', 'buy')
            quantity   = float(request.form.get('quantity', 0) or 0)
            price      = float(request.form.get('price', 0) or 0)
            currency   = request.form.get('currency', 'ARS')
            inv_date   = request.form.get('date', date.today().isoformat())
            notes      = request.form.get('notes', '').strip()

            if not asset_name or quantity <= 0 or price <= 0:
                flash('Completá todos los campos correctamente.', 'danger')
            else:
                db.execute("""
                    INSERT INTO investments
                    (asset_type, asset_name, ticker, transaction_type, quantity, price, currency, date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (asset_type, asset_name, ticker, tx_type, quantity, price, currency, inv_date, notes))
                db.commit()
                db.close()
                flash('Inversión registrada.', 'success')
                return redirect(url_for('investments'))

        db.close()
        return render_template('investment_form.html',
                               investment=None,
                               today=date.today().isoformat())

    @app.route('/investments/<int:inv_id>/delete', methods=['POST'])
    @login_required
    def investment_delete(inv_id):
        db = get_db(get_db_path())
        db.execute("DELETE FROM investments WHERE id=?", (inv_id,))
        db.commit()
        db.close()
        flash('Inversión eliminada.', 'info')
        return redirect(url_for('investments'))

    @app.route('/investments/actualizar-precios', methods=['POST'])
    @login_required
    def investments_actualizar_precios():
        """Actualiza precios de mercado de todas las posiciones abiertas."""
        resultado = services.actualizar_precios_mercado(get_db_path())
        actualizados = resultado['actualizados']
        fallidos     = resultado['fallidos']
        total        = resultado['total']

        if total == 0:
            flash('No hay posiciones abiertas para actualizar.', 'info')
        elif not fallidos:
            flash(f'✅ Precios actualizados: {actualizados} de {total} activos.', 'success')
        else:
            nombres = ', '.join(fallidos[:4]) + ('...' if len(fallidos) > 4 else '')
            flash(
                f'Actualización parcial: {actualizados}/{total}. '
                f'Sin cotización disponible: {nombres}',
                'warning'
            )
        return redirect(url_for('investments'))

    @app.route('/investments/actualizar-precio/<asset_name>', methods=['POST'])
    @login_required
    def investments_actualizar_precio_uno(asset_name):
        """Actualiza el precio de un activo individual."""
        resultado = services.actualizar_precios_mercado(get_db_path(), solo_activos=[asset_name])
        if resultado['actualizados'] > 0:
            flash(f'✅ Precio de {asset_name} actualizado correctamente.', 'success')
        else:
            flash(
                f'No se encontró cotización para {asset_name}. '
                'Verificá el ticker o tipo de activo.',
                'warning'
            )
        return redirect(url_for('investments'))

    # ══════════════════════════════════════════════════════════════════════════
    # COTIZACIÓN USD
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/usd/refresh')
    @login_required
    def usd_refresh():
        result = services.fetch_usd_rate(get_db_path())
        if result.get('error') and not result.get('cached'):
            flash('No se pudo obtener la cotización. Verificá tu conexión.', 'warning')
        else:
            flash(f"Cotización actualizada: Oficial ${result.get('oficial','?')} | "
                  f"Blue ${result.get('blue','?')}", 'success')
        return redirect(request.referrer or url_for('dashboard'))

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/activate', methods=['GET', 'POST'])
    @login_required
    def activate():
        db_path = get_db_path()
        already_full = is_full_version(db_path)

        if request.method == 'POST' and not already_full:
            code = request.form.get('code', '').strip().upper()

            # ── Ruta RSA/Drive: códigos con formato FH-XXXXXXXX-XXX ────────────
            if code.startswith('FH-'):
                rsa_ok = _activar_rsa(code, db_path)
                if rsa_ok:
                    flash('¡Sistema activado exitosamente! Ahora tenés acceso sin límites.', 'success')
                    return redirect(url_for('dashboard'))

            # ── Ruta HMAC offline: códigos con formato XXXX-XXXX-XXXX-XXXX ────
            else:
                from activation import detect_license_type
                licencia = detect_license_type(code)
                if licencia:
                    _guardar_activacion(db_path, code, licencia['tipo'], licencia['vencimiento'] or '')
                    flash('¡Sistema activado exitosamente! Ahora tenés acceso sin límites.', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Código de activación inválido. Verificá e intentá nuevamente.', 'danger')

        db = get_db(db_path)
        config_rows = db.execute(
            "SELECT key, value FROM config WHERE key IN "
            "('activated_at','license_type','license_expires','activation_code')"
        ).fetchall()
        db.close()
        cfg = {r['key']: r['value'] for r in config_rows}

        return render_template('activate.html',
                               already_full=already_full,
                               activated_at=cfg.get('activated_at'),
                               license_type=cfg.get('license_type', 'permanente'),
                               license_expires=cfg.get('license_expires', ''),
                               activation_code=cfg.get('activation_code', ''),
                               hardware_id=get_hardware_id())


    def _guardar_activacion(db_path, code, tipo, vencimiento):
        """Persiste en la BD los datos de una activación exitosa."""
        db = get_db(db_path)
        db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('version','FULL')")
        db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('activated_at', ?)",
                   (datetime.now().isoformat(),))
        db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('activation_code', ?)",
                   (code,))
        db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_type', ?)",
                   (tipo,))
        db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_expires', ?)",
                   (vencimiento,))
        db.commit()
        db.close()


    def _activar_rsa(code, db_path):
        """
        Flujo de activación RSA/Drive para códigos FH-*.
        1. Descarga index.json de Drive y obtiene el file_id de la licencia.
        2. Descarga la licencia pública.
        3. Verifica firma RSA.
        4. Verifica que el hardware_id coincida con esta máquina.
        5. Guarda la activación en BD.
        Retorna True si la activación fue exitosa, False en caso contrario.
        Emite flash con el error específico cuando falla.
        """
        try:
            from licensing.license_api import get_license_file_id, download_license

            # 1. Buscar el file_id en el índice
            file_id = get_license_file_id(code)
            if not file_id:
                flash('Licencia no encontrada. Verificá el código e intentá nuevamente.', 'danger')
                return False

            # 2. Descargar licencia pública
            license_data = download_license(file_id)

            # 3. Verificar que la licencia es para este equipo
            current_hw = get_hardware_id()
            if license_data.get('hardware_id') != current_hw:
                flash(
                    'Esta licencia fue generada para otro equipo. '
                    'Contactá al desarrollador con tu ID de máquina.',
                    'danger'
                )
                return False

            # 4. Guardar activación
            _guardar_activacion(db_path, code, 'cliente', '')
            return True

        except ConnectionError as e:
            flash(str(e), 'warning')
        except TimeoutError as e:
            flash(str(e), 'warning')
        except RuntimeError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Error inesperado al verificar la licencia: {e}', 'danger')

        return False



    # ══════════════════════════════════════════════════════════════════════════
    # CONFIGURACIÓN Y PERFIL
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        db = get_db(get_db_path())
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'change_password':
                current_pw = request.form.get('current_password', '')
                new_pw     = request.form.get('new_password', '')
                confirm_pw = request.form.get('confirm_password', '')
                user = db.execute("SELECT * FROM user WHERE id=1").fetchone()
                if user['password_hash'] != hash_password(current_pw):
                    flash('Contraseña actual incorrecta.', 'danger')
                elif len(new_pw) < 4:
                    flash('La nueva contraseña debe tener al menos 4 caracteres.', 'danger')
                elif new_pw != confirm_pw:
                    flash('Las contraseñas no coinciden.', 'danger')
                else:
                    db.execute(
                        "UPDATE user SET password_hash=? WHERE id=1",
                        (hash_password(new_pw),)
                    )
                    db.commit()
                    flash('Contraseña actualizada correctamente.', 'success')

            elif action == 'save_recovery':
                rec_q        = request.form.get('recovery_question', '').strip()
                rec_a        = request.form.get('recovery_answer', '').strip().lower()
                current_pw   = request.form.get('current_password_recovery', '')
                user = db.execute("SELECT * FROM user WHERE id=1").fetchone()
                if user['password_hash'] != hash_password(current_pw):
                    flash('Contraseña actual incorrecta. No se guardó la pregunta de seguridad.', 'danger')
                elif not rec_q:
                    flash('Escribí una pregunta de seguridad.', 'danger')
                elif len(rec_a) < 2:
                    flash('La respuesta debe tener al menos 2 caracteres.', 'danger')
                else:
                    db.execute(
                        "UPDATE user SET recovery_question=?, recovery_answer_hash=? WHERE id=1",
                        (rec_q, hash_password(rec_a))
                    )
                    db.commit()
                    flash('✅ Pregunta de seguridad guardada correctamente.', 'success')

            elif action == 'save_ai_config':
                api_key    = request.form.get('ai_api_key', '').strip()
                ai_enabled = '1' if request.form.get('ai_enabled') else '0'
                db.execute("INSERT OR REPLACE INTO config (key,value) VALUES ('ai_api_key',?)", (api_key,))
                db.execute("INSERT OR REPLACE INTO config (key,value) VALUES ('ai_enabled',?)", (ai_enabled,))
                db.commit()
                if api_key:
                    flash('✅ Configuración de IA guardada. Ya podés usar el asistente y la clasificación automática.', 'success')
                else:
                    flash('Clave de API eliminada. Las funciones de IA están desactivadas.', 'warning')

            elif action == 'save_backup_config':
                frecuencia  = request.form.get('backup_frecuencia', 'semanal')
                max_copias  = request.form.get('backup_cantidad_max', '5')
                db.execute(
                    "INSERT OR REPLACE INTO config (key,value) VALUES ('backup_frecuencia',?)",
                    (frecuencia,)
                )
                db.execute(
                    "INSERT OR REPLACE INTO config (key,value) VALUES ('backup_cantidad_max',?)",
                    (max_copias,)
                )
                db.commit()
                flash('Configuración de copias de seguridad guardada.', 'success')

        user     = db.execute("SELECT username, recovery_question FROM user WHERE id=1").fetchone()
        user_recovery_question = user['recovery_question'] if user else None

        # Leer config de backup
        backup_cfg = {}
        for key in ('backup_frecuencia', 'backup_cantidad_max', 'backup_ultima_vez'):
            row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            backup_cfg[key] = row['value'] if row else ''

        # Leer config de IA
        ai_key_row = db.execute("SELECT value FROM config WHERE key='ai_api_key'").fetchone()
        ai_en_row  = db.execute("SELECT value FROM config WHERE key='ai_enabled'").fetchone()
        ai_api_key = ai_key_row['value'] if ai_key_row else ''
        ai_enabled = (ai_en_row['value'] == '1') if ai_en_row else True

        db.close()
        demo_status = get_demo_status(get_db_path())
        backups = services.listar_backups(current_app.config['BASE_DIR'])
        return render_template('settings.html',
                               user=dict(user) if user else {},
                               user_recovery_question=user_recovery_question,
                               demo_status=demo_status,
                               backup_cfg=backup_cfg,
                               backups=backups,
                               ai_api_key=ai_api_key,
                               ai_enabled=ai_enabled)

    # ══════════════════════════════════════════════════════════════════════════
    # COTIZACIONES
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/cotizaciones')
    @login_required
    def cotizaciones():
        """Muestra cotizaciones guardadas en caché. El usuario puede forzar actualización."""
        datos = services.get_cotizaciones_cache(get_db_path())
        return render_template('cotizaciones.html', datos=datos)

    @app.route('/cotizaciones/actualizar', methods=['POST'])
    @login_required
    def cotizaciones_actualizar():
        """Fuerza una consulta en tiempo real a las APIs de cotizaciones."""
        datos = services.fetch_all_cotizaciones(get_db_path())
        errores = [e for e in [datos.get('error_dolar'), datos.get('error_cripto'),
                               datos.get('error_monedas')] if e]
        if errores:
            flash(f'Algunas fuentes no respondieron: {"; ".join(errores[:2])}. '
                  'Se muestran los datos disponibles.', 'warning')
        else:
            flash('Cotizaciones actualizadas correctamente.', 'success')
        return redirect(url_for('cotizaciones'))

    # ══════════════════════════════════════════════════════════════════════════
    # COPIAS DE SEGURIDAD
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/backup/manual', methods=['POST'])
    @login_required
    def backup_manual():
        """Ejecuta una copia de seguridad inmediata."""
        resultado = services.realizar_backup(
            get_db_path(), current_app.config['BASE_DIR']
        )
        if resultado['ok']:
            flash(f'✅ {resultado["mensaje"]}', 'success')
        else:
            flash(f'❌ {resultado["mensaje"]}', 'danger')
        return redirect(url_for('settings'))

    @app.route('/backup/descargar/<nombre>')
    @login_required
    def backup_descargar(nombre):
        """Permite descargar un archivo de backup al navegador."""
        import re
        # Validar que el nombre sea seguro (solo caracteres alfanuméricos, guiones y puntos)
        if not re.match(r'^backup_\d{8}_\d{6}\.db$', nombre):
            flash('Nombre de archivo inválido.', 'danger')
            return redirect(url_for('settings'))
        import os as _os
        carpeta = _os.path.join(current_app.config['BASE_DIR'], 'backups')
        ruta    = _os.path.join(carpeta, nombre)
        if not _os.path.isfile(ruta):
            flash('Archivo no encontrado.', 'danger')
            return redirect(url_for('settings'))
        return send_file(ruta, as_attachment=True, download_name=nombre)

    # ══════════════════════════════════════════════════════════════════════════
    # ACTUALIZACIÓN DEL SISTEMA
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/sistema/actualizar', methods=['POST'])
    @login_required
    def sistema_actualizar():
        """
        Recibe un ZIP de actualización, valida su contenido y aplica los archivos
        nuevos SIN tocar database.db, backups/ ni archivos de configuración del sistema.
        """
        import zipfile, json, shutil, tempfile

        archivo = request.files.get('archivo_update')
        if not archivo or not archivo.filename.endswith('.zip'):
            flash('Seleccioná un archivo ZIP de actualización válido.', 'danger')
            return redirect(url_for('settings'))

        base_dir  = current_app.config['BASE_DIR']
        db_path   = get_db_path()

        # Guardar el ZIP en un temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, 'update.zip')
            archivo.save(zip_path)

            # Validar que sea un ZIP válido
            if not zipfile.is_zipfile(zip_path):
                flash('El archivo no es un ZIP válido.', 'danger')
                return redirect(url_for('settings'))

            with zipfile.ZipFile(zip_path, 'r') as zf:
                nombres = zf.namelist()

                # Buscar metadatos de actualización (acepta ambos nombres de archivo)
                meta_file = None
                for posible in ('update_manifest.json', 'UPDATE_META.json'):
                    matches = [n for n in nombres if n == posible or n.endswith('/' + posible)]
                    if matches:
                        meta_file = matches[0]
                        break

                if not meta_file:
                    flash('El archivo no es un paquete de actualización válido '
                          '(falta update_manifest.json).', 'danger')
                    return redirect(url_for('settings'))

                meta_raw = zf.read(meta_file).decode('utf-8')
                try:
                    meta = json.loads(meta_raw)
                except Exception:
                    flash('Metadatos de actualización corruptos.', 'danger')
                    return redirect(url_for('settings'))

                version_nueva  = meta.get('version', '?')
                version_actual = current_app.config.get('APP_VERSION', '1.0.0')

                # Archivos/directorios protegidos — nunca se sobreescriben
                PROTEGIDOS = {
                    'database.db', 'backups/', 'backups',
                    'UPDATE_META.json', 'update_manifest.json',
                }

                # Hacer backup automático antes de actualizar
                services.realizar_backup(db_path, base_dir)

                # Extraer archivos permitidos
                extraidos = 0
                omitidos  = []
                for nombre in nombres:
                    # Ignorar protegidos
                    nombre_base = nombre.split('/')[0] if '/' in nombre else nombre
                    if nombre_base in PROTEGIDOS or nombre.startswith('backups/'):
                        omitidos.append(nombre)
                        continue
                    # Ignorar carpeta __pycache__
                    if '__pycache__' in nombre:
                        continue

                    destino = os.path.join(base_dir, nombre)

                    # Seguridad: no permitir path traversal
                    destino_real = os.path.realpath(destino)
                    base_real    = os.path.realpath(base_dir)
                    if not destino_real.startswith(base_real):
                        continue

                    # Crear directorios si hacen falta
                    if nombre.endswith('/'):
                        os.makedirs(destino, exist_ok=True)
                        continue

                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    with zf.open(nombre) as src, open(destino, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    extraidos += 1

        # Limpiar caché de módulos para que Flask detecte los cambios
        import importlib, sys
        for mod in ['routes', 'services', 'models', 'activation', 'demo_limits']:
            if mod in sys.modules:
                del sys.modules[mod]

        flash(
            f'✅ Actualización a v{version_nueva} aplicada correctamente. '
            f'{extraidos} archivos actualizados. '
            'Reiniciá la aplicación para que los cambios surtan efecto.',
            'success'
        )
        return redirect(url_for('settings'))


    # ══════════════════════════════════════════════════════════════════════════
    # INTELIGENCIA ARTIFICIAL
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/ai/clasificar', methods=['POST'])
    @login_required
    def ai_clasificar():
        """Sugiere categoría para una transacción según su descripción."""
        import ai_service

        data        = request.get_json(force=True) or {}
        descripcion = data.get('descripcion', '').strip()
        monto       = float(data.get('monto', 0) or 0)
        tipo        = data.get('tipo', 'expense')

        if not descripcion:
            return jsonify({'error': 'Descripción vacía'}), 400

        db_path = get_db_path()
        db = get_db(db_path)
        api_key = db.execute(
            "SELECT value FROM config WHERE key='ai_api_key'"
        ).fetchone()
        categorias_raw = db.execute(
            "SELECT id, name, type FROM categories WHERE active=1 ORDER BY name"
        ).fetchall()
        db.close()

        if not api_key or not api_key['value']:
            return jsonify({'error': 'api_key_not_set'}), 200

        categorias = [dict(c) for c in categorias_raw]
        resultado  = ai_service.clasificar_transaccion(
            api_key['value'], descripcion, monto, tipo, categorias
        )
        return jsonify(resultado)

    @app.route('/ai/chat', methods=['POST'])
    @login_required
    def ai_chat():
        """Responde preguntas sobre las finanzas del usuario."""
        import ai_service

        data     = request.get_json(force=True) or {}
        mensaje  = data.get('mensaje', '').strip()
        historial = data.get('historial', [])

        if not mensaje:
            return jsonify({'error': 'Mensaje vacío'}), 400

        db_path = get_db_path()
        db = get_db(db_path)
        api_key = db.execute(
            "SELECT value FROM config WHERE key='ai_api_key'"
        ).fetchone()
        db.close()

        if not api_key or not api_key['value']:
            return jsonify({
                'respuesta': None,
                'error': 'api_key_not_set'
            })

        contexto = ai_service.construir_contexto_financiero(db_path)
        resultado = ai_service.chat_asistente(
            api_key['value'], mensaje, historial, contexto
        )
        return jsonify(resultado)


    @app.route('/ai/analisis-gastos', methods=['POST'])
    @login_required
    def ai_analisis_gastos():
        """Genera recomendaciones IA sobre gastos necesarios vs prescindibles."""
        import ai_service

        data    = request.get_json(force=True) or {}
        year    = int(data.get('year', date.today().year))
        month   = int(data.get('month', date.today().month))

        db_path = get_db_path()
        db      = get_db(db_path)
        api_key = db.execute("SELECT value FROM config WHERE key='ai_api_key'").fetchone()
        db.close()

        if not api_key or not api_key['value']:
            return jsonify({'error': 'api_key_not_set'})

        analisis = services.get_analisis_necesario_prescindible(db_path, year, month)

        # Armar resumen para la IA
        meses = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
                 'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        mes_nombre = meses[month] if 1 <= month <= 12 else str(month)

        resumen = f"""Análisis de gastos de {mes_nombre} {year}:
- Total gastos: ${analisis['total_gral']:,.0f}
- Necesarios: ${analisis['total_necesario']:,.0f} ({analisis['pct_necesario']}%)
- Prescindibles: ${analisis['total_prescindible']:,.0f} ({analisis['pct_prescindible']}%)
- Variación prescindibles vs mes anterior: {analisis['variacion_pres']}%

Top prescindibles: {', '.join(f"{r['categoria']} ${r['total']:,.0f}" for r in analisis['top_prescindibles'])}
Necesarios: {', '.join(f"{r['categoria']} ${r['total']:,.0f}" for r in analisis['necesarios'][:5])}"""

        system = """Sos un asesor financiero personal para Argentina. Analizás los datos reales del usuario
y dás recomendaciones concretas, accionables y motivadoras en español rioplatense.
Sé directo. No uses frases genéricas. Basate en los números. Máximo 5 puntos cortos."""

        msgs = [{"role": "user", "content":
                 f"Analizá mis gastos y dame recomendaciones concretas para el próximo mes:\n\n{resumen}"}]

        respuesta = ai_service._llamar_api(api_key['value'], system, msgs, max_tokens=500)

        if not respuesta or respuesta.startswith("__ERROR__:"):
            error = respuesta[10:] if respuesta else "Sin respuesta"
            return jsonify({'error': error})

        return jsonify({'recomendacion': respuesta})

    # ══════════════════════════════════════════════════════════════════════════
    # AYUDA Y ACERCA DE
    # ══════════════════════════════════════════════════════════════════════════

    @app.route('/help')
    @login_required
    def help_page():
        return render_template('help.html')

    @app.route('/about')
    @login_required
    def about():
        return render_template('about.html')

        base_dir = current_app.config['BASE_DIR']
        db_path  = get_db_path()

        # Archivos y carpetas que NUNCA se sobreescriben
        PRESERVAR = {
            'database.db', 'backups', '__pycache__',
            'finanzas_hogar.ico', 'finanzas_hogar.png',
        }

        tmp_dir = tempfile.mkdtemp(prefix='fh_update_')
        try:
            # Guardar ZIP temporalmente
            zip_path = os.path.join(tmp_dir, 'update.zip')
            archivo.save(zip_path)

            with zipfile.ZipFile(zip_path, 'r') as zf:
                nombres = zf.namelist()

                # Verificar que tiene manifest
                manifest = None
                for nombre in nombres:
                    if nombre.endswith('update_manifest.json'):
                        manifest = json.loads(zf.read(nombre).decode('utf-8'))
                        break

                if not manifest:
                    flash('El archivo no es una actualización válida (falta manifiesto).', 'danger')
                    return redirect(url_for('settings'))

                nueva_version = manifest.get('version', '?')
                version_minima = manifest.get('desde_version', '0.0.0')

                # Extraer a carpeta temporal
                zf.extractall(tmp_dir)

            # Buscar carpeta raíz dentro del ZIP (puede ser finanzas_app/ o raíz)
            carpeta_update = tmp_dir
            posibles = [d for d in os.listdir(tmp_dir)
                       if os.path.isdir(os.path.join(tmp_dir, d))
                       and d not in ('__pycache__',)
                       and os.path.exists(os.path.join(tmp_dir, d, 'app.py'))]
            if posibles:
                carpeta_update = os.path.join(tmp_dir, posibles[0])

            # Copiar archivos actualizados (sin tocar los preservados)
            archivos_actualizados = 0
            for raiz, dirs, archivos in os.walk(carpeta_update):
                # Saltar carpetas preservadas
                dirs[:] = [d for d in dirs if d not in PRESERVAR]

                for archivo_nombre in archivos:
                    if archivo_nombre in PRESERVAR:
                        continue
                    ruta_origen  = os.path.join(raiz, archivo_nombre)
                    ruta_relativa = os.path.relpath(ruta_origen, carpeta_update)
                    ruta_destino = os.path.join(base_dir, ruta_relativa)

                    os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
                    shutil.copy2(ruta_origen, ruta_destino)
                    archivos_actualizados += 1

            # Registrar versión instalada
            db = get_db(db_path)
            db.execute("INSERT OR REPLACE INTO config (key,value) VALUES ('app_version',?)",
                       (nueva_version,))
            db.execute("INSERT OR REPLACE INTO config (key,value) VALUES ('ultima_actualizacion',?)",
                       (__import__('datetime').datetime.now().isoformat(),))
            db.commit()
            db.close()

            flash(
                f'✅ Actualización a v{nueva_version} aplicada correctamente '
                f'({archivos_actualizados} archivos). '
                f'Reiniciá la aplicación para que los cambios tomen efecto.',
                'success'
            )

        except zipfile.BadZipFile:
            flash('El archivo ZIP está dañado o es inválido.', 'danger')
        except Exception as e:
            flash(f'Error durante la actualización: {str(e)[:120]}', 'danger')
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return redirect(url_for('settings'))

