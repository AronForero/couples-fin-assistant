import psycopg2.extras

from .connection import get_conn


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


def update_user_chat_id(user_id: int, chat_id: int) -> bool:
    sql = "UPDATE users SET chat_id = %s WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (chat_id, user_id))
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def update_user_status(user_id: int, status: str) -> bool:
    sql = "UPDATE users SET status = %s, status_updated_at = NOW() WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, user_id))
            updated = cur.rowcount > 0
        conn.commit()
    return updated


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
