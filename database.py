import csv
import io
import psycopg2
import psycopg2.extras
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD,
)

_DSN = {
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT,
    "dbname": POSTGRES_DB,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
}

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

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT        NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

_SEED_SPLIT = """
INSERT INTO settings (key, value) VALUES ('split_aru', '0.63') ON CONFLICT DO NOTHING;
INSERT INTO settings (key, value) VALUES ('split_mon', '0.37') ON CONFLICT DO NOTHING;
"""

_CSV_COLUMNS = [
    "id", "fecha", "quien_pago", "subcategoria", "categoria",
    "concepto", "valor", "compartida", "valor_a_pagar", "observacion",
]


def get_conn():
    return psycopg2.connect(**_DSN)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_EXPENSES)
            cur.execute(_CREATE_SETTINGS)
            cur.execute(_SEED_SPLIT)
        conn.commit()


# ── Expenses ──────────────────────────────────────────────────────────────────

def insert_expense(expense: dict) -> int:
    sql = """
        INSERT INTO expenses
            (fecha, quien_pago, subcategoria, categoria, concepto,
             valor, compartida, valor_a_pagar, observacion)
        VALUES
            (%(fecha)s, %(quien_pago)s, %(subcategoria)s, %(categoria)s, %(concepto)s,
             %(valor)s, %(compartida)s, %(valor_a_pagar)s, %(observacion)s)
        RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, expense)
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def get_expenses_by_month(year: int, month: int) -> list[dict]:
    sql = """
        SELECT id, fecha, quien_pago, subcategoria, categoria,
               concepto, valor, compartida, valor_a_pagar, observacion
        FROM expenses
        WHERE EXTRACT(YEAR  FROM fecha) = %s
          AND EXTRACT(MONTH FROM fecha) = %s
        ORDER BY fecha, id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (year, month))
            return [dict(row) for row in cur.fetchall()]


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str) -> str:
    sql = "SELECT value FROM settings WHERE key = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (key,))
            row = cur.fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    sql = """
        INSERT INTO settings (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (key, value))
        conn.commit()


def get_split() -> tuple[float, float]:
    aru = float(get_setting("split_aru", "0.63"))
    mon = float(get_setting("split_mon", "0.37"))
    return aru, mon
