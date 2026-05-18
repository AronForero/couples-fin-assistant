import logging
import secrets
import psycopg2
import psycopg2.extras
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD,
)

logger = logging.getLogger(__name__)

_DSN = {
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT,
    "dbname": POSTGRES_DB,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
}

# ── Table DDL ─────────────────────────────────────────────────────────────────

_CREATE_EXPENSES = """
CREATE TABLE IF NOT EXISTS expenses (
    id            SERIAL PRIMARY KEY,
    fecha         DATE         NOT NULL,
    quien_pago    VARCHAR(3)   NOT NULL,
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,
    compartida    VARCHAR(2)   NOT NULL,
    valor_a_pagar NUMERIC(12,2),
    observacion   TEXT,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
"""

_CREATE_COUPLES = """
CREATE TABLE IF NOT EXISTS couples (
    id          SERIAL PRIMARY KEY,
    invite_code VARCHAR(8) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(50) NOT NULL,
    couple_id     INTEGER REFERENCES couples(id),
    chat_id       BIGINT UNIQUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_COUPLE_SETTINGS = """
CREATE TABLE IF NOT EXISTS couple_settings (
    couple_id        INTEGER NOT NULL REFERENCES couples(id),
    user_id          INTEGER NOT NULL REFERENCES users(id),
    split_percentage NUMERIC(5,4) NOT NULL,
    PRIMARY KEY (couple_id, user_id)
);
"""

_ADD_EXPENSE_COLUMNS = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='expenses' AND column_name='quien_pago_id') THEN
        ALTER TABLE expenses ADD COLUMN quien_pago_id INTEGER REFERENCES users(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='expenses' AND column_name='debt_user_id') THEN
        ALTER TABLE expenses ADD COLUMN debt_user_id INTEGER REFERENCES users(id);
    END IF;
END$$;
"""

_CSV_COLUMNS = [
    "id", "fecha", "quien_pago", "subcategoria", "categoria",
    "concepto", "valor", "compartida", "valor_a_pagar", "observacion",
]

# ── Connection ────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**_DSN)


# ── Init & Seed ───────────────────────────────────────────────────────────────

def _generate_invite_code() -> str:
    return secrets.token_urlsafe(6)[:8].upper()


def _seed_default_couple(cur) -> tuple[int, int, int] | None:
    """Create default couple + Aru/Mon users if they don't exist.
    Returns (couple_id, aru_id, mon_id) or None if already seeded."""
    cur.execute("SELECT id FROM users WHERE display_name = 'Aru' LIMIT 1")
    existing = cur.fetchone()
    if existing:
        cur.execute("SELECT id FROM users WHERE display_name = 'Mon' LIMIT 1")
        mon_row = cur.fetchone()
        cur.execute("SELECT couple_id FROM users WHERE id = %s", (existing[0],))
        couple_row = cur.fetchone()
        return (couple_row[0], existing[0], mon_row[0]) if couple_row and mon_row else None

    invite_code = _generate_invite_code()
    cur.execute("INSERT INTO couples (invite_code) VALUES (%s) RETURNING id", (invite_code,))
    couple_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("aru@finbot.local", "!", "Aru", couple_id, 247795192),
    )
    aru_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("mon@finbot.local", "!", "Mon", couple_id, 1560352087),
    )
    mon_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO couple_settings (couple_id, user_id, split_percentage) VALUES (%s, %s, %s)",
        (couple_id, aru_id, 0.63),
    )
    cur.execute(
        "INSERT INTO couple_settings (couple_id, user_id, split_percentage) VALUES (%s, %s, %s)",
        (couple_id, mon_id, 0.37),
    )

    return (couple_id, aru_id, mon_id)


def _migrate_expenses(cur, aru_id: int, mon_id: int):
    """Set quien_pago_id and debt_user_id on existing expenses."""
    cur.execute(
        """UPDATE expenses SET quien_pago_id = %s WHERE quien_pago = 'Aru' AND quien_pago_id IS NULL""",
        (aru_id,),
    )
    cur.execute(
        """UPDATE expenses SET quien_pago_id = %s WHERE quien_pago = 'Mon' AND quien_pago_id IS NULL""",
        (mon_id,),
    )
    cur.execute(
        """UPDATE expenses SET debt_user_id = %s WHERE observacion LIKE '%%Aru Debe%%' AND debt_user_id IS NULL""",
        (aru_id,),
    )
    cur.execute(
        """UPDATE expenses SET debt_user_id = %s WHERE observacion LIKE '%%Mon Debe%%' AND debt_user_id IS NULL""",
        (mon_id,),
    )


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_EXPENSES)
            cur.execute(_CREATE_COUPLES)
            cur.execute(_CREATE_USERS)
            cur.execute(_CREATE_COUPLE_SETTINGS)
            cur.execute(_ADD_EXPENSE_COLUMNS)

            ids = _seed_default_couple(cur)
            if ids:
                _migrate_expenses(cur, ids[1], ids[2])
        conn.commit()
    logger.info("Database initialised")


# ── Users ─────────────────────────────────────────────────────────────────────

def create_couple(invite_code: str | None = None) -> int:
    if invite_code is None:
        invite_code = _generate_invite_code()
    sql = "INSERT INTO couples (invite_code) VALUES (%s) RETURNING id"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (invite_code,))
            couple_id = cur.fetchone()[0]
        conn.commit()
    return couple_id


def create_user(
    email: str,
    password_hash: str,
    display_name: str,
    couple_id: int | None = None,
    chat_id: int | None = None,
) -> int:
    sql = """
        INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, password_hash, display_name, couple_id, chat_id))
            user_id = cur.fetchone()[0]
        conn.commit()
    return user_id


def join_couple(user_id: int, invite_code: str) -> bool:
    sql = "SELECT id FROM couples WHERE invite_code = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (invite_code,))
            row = cur.fetchone()
            if not row:
                return False
            couple_id = row[0]
            cur.execute("UPDATE users SET couple_id = %s WHERE id = %s", (couple_id, user_id))
        conn.commit()
    return True


def get_user_by_id(user_id: int) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, created_at FROM users WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    sql = "SELECT id, email, password_hash, display_name, couple_id, chat_id, created_at FROM users WHERE email = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_display_name(display_name: str) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, created_at FROM users WHERE display_name = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (display_name,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_chat_id(chat_id: int) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, created_at FROM users WHERE chat_id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (chat_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def update_user_chat_id(user_id: int, chat_id: int) -> bool:
    sql = "UPDATE users SET chat_id = %s WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (chat_id, user_id))
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def get_couple_users(couple_id: int) -> list[dict]:
    sql = "SELECT id, email, display_name, couple_id, chat_id FROM users WHERE couple_id = %s ORDER BY id"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (couple_id,))
            return [dict(row) for row in cur.fetchall()]


def get_partner(user_id: int) -> dict | None:
    user = get_user_by_id(user_id)
    if not user or not user.get("couple_id"):
        return None
    sql = """
        SELECT id, email, display_name, couple_id, chat_id
        FROM users
        WHERE couple_id = %s AND id != %s
        LIMIT 1
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user["couple_id"], user_id))
            row = cur.fetchone()
    return dict(row) if row else None


def get_all_chat_ids() -> set[int]:
    sql = "SELECT chat_id FROM users WHERE chat_id IS NOT NULL"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return {row[0] for row in cur.fetchall()}


# ── Couple Settings ───────────────────────────────────────────────────────────

def get_split_for_couple(couple_id: int) -> dict[int, float]:
    """Returns {user_id: split_percentage} for a couple."""
    sql = "SELECT user_id, split_percentage FROM couple_settings WHERE couple_id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (couple_id,))
            return {row[0]: float(row[1]) for row in cur.fetchall()}


def update_split_for_couple(couple_id: int, splits: dict[int, float]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            for user_id, pct in splits.items():
                cur.execute(
                    """INSERT INTO couple_settings (couple_id, user_id, split_percentage)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (couple_id, user_id)
                       DO UPDATE SET split_percentage = EXCLUDED.split_percentage""",
                    (couple_id, user_id, pct),
                )
        conn.commit()


# ── Expenses ──────────────────────────────────────────────────────────────────

def insert_expense(expense: dict) -> int:
    sql = """
        INSERT INTO expenses
            (fecha, quien_pago, subcategoria, categoria, concepto,
             valor, compartida, valor_a_pagar, observacion,
             quien_pago_id, debt_user_id)
        VALUES
            (%(fecha)s, %(quien_pago)s, %(subcategoria)s, %(categoria)s, %(concepto)s,
             %(valor)s, %(compartida)s, %(valor_a_pagar)s, %(observacion)s,
             %(quien_pago_id)s, %(debt_user_id)s)
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


def get_expenses_by_month(year: int, month: int) -> list[dict]:
    sql = """
        SELECT id, fecha, quien_pago, subcategoria, categoria,
               concepto, valor, compartida, valor_a_pagar, observacion,
               quien_pago_id, debt_user_id
        FROM expenses
        WHERE EXTRACT(YEAR  FROM fecha) = %s
          AND EXTRACT(MONTH FROM fecha) = %s
        ORDER BY fecha, id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month))
            return [dict(row) for row in cur.fetchall()]


def get_expenses_by_month_and_users(year: int, month: int, user_ids: list[int]) -> list[dict]:
    sql = """
        SELECT id, fecha, quien_pago, subcategoria, categoria,
               concepto, valor, compartida, valor_a_pagar, observacion,
               quien_pago_id, debt_user_id
        FROM expenses
        WHERE EXTRACT(YEAR  FROM fecha) = %s
          AND EXTRACT(MONTH FROM fecha) = %s
          AND quien_pago_id = ANY(%s)
        ORDER BY fecha, id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month, user_ids))
            return [dict(row) for row in cur.fetchall()]


def get_expense_by_id(expense_id: int) -> dict | None:
    sql = """
        SELECT id, fecha, quien_pago, subcategoria, categoria,
               concepto, valor, compartida, valor_a_pagar, observacion,
               quien_pago_id, debt_user_id
        FROM expenses
        WHERE id = %s
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


def get_recent_expenses(limit: int = 5) -> list[dict]:
    sql = """
        SELECT id, fecha, quien_pago, subcategoria, categoria,
               concepto, valor, compartida, valor_a_pagar, observacion,
               quien_pago_id, debt_user_id
        FROM expenses
        ORDER BY id DESC
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            return [dict(row) for row in cur.fetchall()]
