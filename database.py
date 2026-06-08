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
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,
    compartida    VARCHAR(2)   NOT NULL,
    valor_a_pagar NUMERIC(12,2),
    quien_pago_id INTEGER,
    debt_user_id  INTEGER,
    couple_id     INTEGER      REFERENCES couples(id),
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
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(50) NOT NULL,
    couple_id       INTEGER REFERENCES couples(id),
    chat_id         BIGINT UNIQUE,
    status          TEXT DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'suspended')),
    status_updated_at TIMESTAMPTZ DEFAULT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_COUPLE_SETTINGS = """
CREATE TABLE IF NOT EXISTS couple_settings (
    couple_id        INTEGER NOT NULL REFERENCES couples(id),
    user_id          INTEGER NOT NULL REFERENCES users(id),
    split_percentage NUMERIC(5,4) NOT NULL,
    left_at          TIMESTAMPTZ NULL,
    PRIMARY KEY (couple_id, user_id)
);
"""

_CREATE_INCOMES = """
CREATE TABLE IF NOT EXISTS incomes (
    id         SERIAL PRIMARY KEY,
    fecha      DATE         NOT NULL,
    concepto   TEXT         NOT NULL,
    valor      INTEGER      NOT NULL,
    user_id    INTEGER      NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ  DEFAULT NOW()
);
"""

_DROP_OLD_EXPENSE_COLUMNS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='expenses' AND column_name='quien_pago') THEN
        ALTER TABLE expenses DROP COLUMN quien_pago;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='expenses' AND column_name='observacion') THEN
        ALTER TABLE expenses DROP COLUMN observacion;
    END IF;
END$$;
"""

_ADD_COUPLE_ID_TO_EXPENSES = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='expenses' AND column_name='couple_id') THEN
        ALTER TABLE expenses ADD COLUMN couple_id INTEGER REFERENCES couples(id);
    END IF;
END$$;
"""

_ADD_LEFT_AT_TO_COUPLE_SETTINGS = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='couple_settings' AND column_name='left_at') THEN
        ALTER TABLE couple_settings ADD COLUMN left_at TIMESTAMPTZ NULL;
    END IF;
END$$;
"""

_MIGRATE_USERS_STATUS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='users' AND column_name='status') THEN
        UPDATE users SET status = 'active' WHERE status IS NULL;
    END IF;
END$$;
"""

_CSV_COLUMNS = [
    "id", "fecha", "subcategoria", "categoria",
    "concepto", "valor", "compartida", "valor_a_pagar",
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
        ("aru@finduo.local", "$2b$12$ePVXcjHHhzQ8rGJJsgRdYOj8VAC/EA5KziO40pUGQ0VkjdDNIe1gK", "Aru", couple_id, 247795192),
    )
    aru_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("mon@finduo.local", "!", "Mon", couple_id, 1560352087),
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


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. couples — no deps
            cur.execute(_CREATE_COUPLES)
            # 2. users — depends on couples
            cur.execute(_CREATE_USERS)
            # 3. couple_settings — depends on couples + users
            cur.execute(_CREATE_COUPLE_SETTINGS)
            # 4. expenses — depends on couples (via couple_id)
            cur.execute(_CREATE_EXPENSES)
            # 5. incomes — depends on users (via user_id)
            cur.execute(_CREATE_INCOMES)
            # 5. migrations
            cur.execute(_ADD_COUPLE_ID_TO_EXPENSES)
            cur.execute(_ADD_LEFT_AT_TO_COUPLE_SETTINGS)
            cur.execute(_DROP_OLD_EXPENSE_COLUMNS)
            cur.execute(_MIGRATE_USERS_STATUS)

            _seed_default_couple(cur)
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


def get_couple_by_id(couple_id: int) -> dict | None:
    sql = "SELECT id, invite_code, created_at FROM couples WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify couple has at least one active user
            cur.execute(
                "SELECT COUNT(*) FROM couple_settings WHERE couple_id = %s AND left_at IS NULL",
                (couple_id,),
            )
            has_active = cur.fetchone()["count"] > 0
            if not has_active:
                return None

            cur.execute(sql, (couple_id,))
            row = cur.fetchone()
    return dict(row) if row else None


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
            # Add user to couple_settings with default split
            cur.execute(
                """INSERT INTO couple_settings (couple_id, user_id, split_percentage)
                   VALUES (%s, %s, 0.50)
                   ON CONFLICT (couple_id, user_id) DO NOTHING""",
                (couple_id, user_id),
            )
        conn.commit()
    return True


def leave_couple(user_id: int) -> bool:
    """User leaves their current couple. Both users are marked as left — couple becomes historical immediately."""
    user = get_user_by_id(user_id)
    if not user or not user.get("couple_id"):
        return False

    couple_id = user["couple_id"]

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Get partner (before we modify anything)
            cur.execute(
                "SELECT user_id FROM couple_settings WHERE couple_id = %s AND user_id != %s",
                (couple_id, user_id),
            )
            partner_row = cur.fetchone()

            # 2. Mark current user as left
            cur.execute(
                """UPDATE couple_settings
                   SET left_at = NOW()
                   WHERE couple_id = %s AND user_id = %s""",
                (couple_id, user_id),
            )

            # 3. Remove couple_id from current user
            cur.execute(
                "UPDATE users SET couple_id = NULL WHERE id = %s",
                (user_id,),
            )

            # 4. If partner exists, also mark them as left and remove their couple_id
            if partner_row:
                partner_id = partner_row[0]
                cur.execute(
                    """UPDATE couple_settings
                       SET left_at = NOW()
                       WHERE couple_id = %s AND user_id = %s""",
                    (couple_id, partner_id),
                )
                cur.execute(
                    "UPDATE users SET couple_id = NULL WHERE id = %s",
                    (partner_id,),
                )

        conn.commit()
    return True


def get_user_couples(user_id: int) -> list[dict]:
    """Returns all couples a user has been in (active + historical)."""
    sql = """
        SELECT
            c.id AS couple_id,
            partner.display_name AS partner_name,
            c.created_at AS joined_at,
            cs_user.left_at,
            CASE WHEN cs_user.left_at IS NULL THEN true ELSE false END AS is_active,
            COALESCE(SUM(e.valor), 0)::int AS total_spent
        FROM couples c
        JOIN couple_settings cs_user ON cs_user.couple_id = c.id AND cs_user.user_id = %s
        JOIN couple_settings cs_partner ON cs_partner.couple_id = c.id AND cs_partner.user_id != %s
        JOIN users partner ON partner.id = cs_partner.user_id
        LEFT JOIN expenses e ON e.couple_id = c.id
        GROUP BY c.id, partner.display_name, c.created_at, cs_user.left_at
        ORDER BY c.created_at DESC
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_id, user_id))
            return [dict(row) for row in cur.fetchall()]


def get_couple_expenses(couple_id: int) -> list[dict]:
    """Returns all expenses for a specific couple (historical or active)."""
    sql = """
        SELECT e.id, e.fecha, u.display_name AS quien_pago, e.subcategoria, e.categoria,
               e.concepto, e.valor, e.compartida, e.valor_a_pagar,
               e.quien_pago_id, e.debt_user_id, e.couple_id
        FROM expenses e
        LEFT JOIN users u ON u.id = e.quien_pago_id
        WHERE e.couple_id = %s
        ORDER BY e.fecha, e.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (couple_id,))
            return [dict(row) for row in cur.fetchall()]


def get_user_by_id(user_id: int) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, status, status_updated_at, created_at FROM users WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    sql = "SELECT id, email, password_hash, display_name, couple_id, chat_id, status, status_updated_at, created_at FROM users WHERE email = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_display_name(display_name: str) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, status, status_updated_at, created_at FROM users WHERE display_name = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (display_name,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_chat_id(chat_id: int) -> dict | None:
    sql = "SELECT id, email, display_name, couple_id, chat_id, status, status_updated_at, created_at FROM users WHERE chat_id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (chat_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def is_user_active(user: dict) -> bool:
    if user.get("status") == "active":
        return True
    if user.get("status") == "suspended":
        return False
    if user.get("status") == "trial":
        from datetime import datetime, timedelta, timezone
        created = user.get("created_at") or datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < created + timedelta(days=30)
    return False


def update_user_status(user_id: int, status: str) -> bool:
    sql = "UPDATE users SET status = %s, status_updated_at = NOW() WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, user_id))
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def update_user_chat_id(user_id: int, chat_id: int) -> bool:
    sql = "UPDATE users SET chat_id = %s WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (chat_id, user_id))
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def get_couple_users(couple_id: int) -> list[dict]:
    sql = "SELECT id, email, display_name, couple_id, chat_id, status FROM users WHERE couple_id = %s ORDER BY id"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (couple_id,))
            return [dict(row) for row in cur.fetchall()]


def get_partner(user_id: int) -> dict | None:
    user = get_user_by_id(user_id)
    if not user or not user.get("couple_id"):
        return None
    sql = """
        SELECT id, email, display_name, couple_id, chat_id, status
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
    # couple_id is required — do not default to None
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


# ── Incomes ──────────────────────────────────────────────────────────────────

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
