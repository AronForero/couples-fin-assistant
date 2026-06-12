import psycopg2.extras

from .connection import get_conn


def insert_expense(expense: dict) -> int:
    sql = """
        INSERT INTO expenses
            (fecha, subcategoria, categoria, concepto,
             valor, compartida, valor_a_pagar,
             quien_pago_id, debt_user_id, couple_id)
        VALUES
            (%(fecha)s, %(subcategoria)s, %(categoria)s, %(concepto)s,
             %(valor)s, %(compartida)s, %(valor_a_pagar)s,
             %(quien_pago_id)s, %(debt_user_id)s, %(couple_id)s)
        RETURNING id
    """
    expense.setdefault("quien_pago_id", None)
    expense.setdefault("debt_user_id", None)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, expense)
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def get_expenses_by_month(year: int, month: int, couple_id: int) -> list[dict]:
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE EXTRACT(YEAR  FROM e.fecha) = %s
          AND EXTRACT(MONTH FROM e.fecha) = %s
          AND e.couple_id = %s
        ORDER BY e.fecha, e.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month, couple_id))
            return [dict(row) for row in cur.fetchall()]


def get_expenses_by_month_and_users(year: int, month: int, user_ids: list[int], couple_id: int) -> list[dict]:
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE EXTRACT(YEAR  FROM e.fecha) = %s
          AND EXTRACT(MONTH FROM e.fecha) = %s
          AND e.quien_pago_id = ANY(%s)
          AND e.couple_id = %s
        ORDER BY e.fecha, e.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month, user_ids, couple_id))
            return [dict(row) for row in cur.fetchall()]


def get_expenses_by_date_range(couple_id: int, start: str, end: str) -> list[dict]:
    """Returns all expenses for a couple between start and end (inclusive, YYYY-MM-DD)."""
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE e.couple_id = %s
          AND e.fecha BETWEEN %s AND %s
        ORDER BY e.fecha, e.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (couple_id, start, end))
            return [dict(row) for row in cur.fetchall()]


def get_expense_by_id(expense_id: int) -> dict | None:
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE e.id = %s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (expense_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def update_expense(expense_id: int, fields: dict) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    sql = f"UPDATE expenses SET {set_clause} WHERE id = %(id)s"
    fields["id"] = expense_id
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, fields)
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def delete_expense(expense_id: int) -> bool:
    sql = "DELETE FROM expenses WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (expense_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def get_recent_expenses(limit: int, couple_id: int) -> list[dict]:
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE e.couple_id = %s
        ORDER BY e.id DESC
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (couple_id, limit))
            return [dict(row) for row in cur.fetchall()]
