import psycopg2.extras

from .connection import get_conn


def insert_income(income: dict) -> int:
    sql = """
        INSERT INTO incomes (fecha, concepto, valor, user_id)
        VALUES (%(fecha)s, %(concepto)s, %(valor)s, %(user_id)s)
        RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, income)
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def get_incomes_by_month(year: int, month: int, user_id: int) -> list[dict]:
    sql = """
        SELECT id, fecha, concepto, valor, user_id, created_at
        FROM incomes
        WHERE EXTRACT(YEAR  FROM fecha) = %s
          AND EXTRACT(MONTH FROM fecha) = %s
          AND user_id = %s
        ORDER BY fecha, id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month, user_id))
            return [dict(row) for row in cur.fetchall()]


def get_recent_incomes(limit: int, user_id: int) -> list[dict]:
    sql = """
        SELECT id, fecha, concepto, valor, user_id, created_at
        FROM incomes
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_id, limit))
            return [dict(row) for row in cur.fetchall()]


def get_income_by_id(income_id: int) -> dict | None:
    sql = "SELECT id, fecha, concepto, valor, user_id, created_at FROM incomes WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (income_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def update_income(income_id: int, fields: dict) -> bool:
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    sql = f"UPDATE incomes SET {set_clause} WHERE id = %(id)s"
    fields["id"] = income_id
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, fields)
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def delete_income(income_id: int) -> bool:
    sql = "DELETE FROM incomes WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (income_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted
