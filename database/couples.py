import psycopg2.extras

from .connection import get_conn
from .users import get_user_by_id
from .utils import generate_invite_code


def create_couple(invite_code: str | None = None) -> int:
    if invite_code is None:
        invite_code = generate_invite_code()
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
            cur.execute(
                "SELECT COUNT(*) AS count FROM couple_settings WHERE couple_id = %s AND left_at IS NULL",
                (couple_id,),
            )
            has_active = cur.fetchone()["count"] > 0
            if not has_active:
                return None

            cur.execute(sql, (couple_id,))
            row = cur.fetchone()
    return dict(row) if row else None


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
