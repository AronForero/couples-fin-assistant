from .connection import get_conn


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
