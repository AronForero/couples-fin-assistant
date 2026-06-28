import logging

from .connection import get_conn
from .schema import (
    ADD_COUPLE_ID_TO_EXPENSES,
    ADD_LEFT_AT_TO_COUPLE_SETTINGS,
    ADD_UPDATE_ID_TO_EXPENSES,
    ADD_UPDATE_ID_TO_INCOMES,
    CREATE_COUPLE_SETTINGS,
    CREATE_COUPLES,
    CREATE_EXPENSES,
    CREATE_INCOMES,
    CREATE_USERS,
    DROP_OLD_EXPENSE_COLUMNS,
    MIGRATE_USERS_STATUS,
)
from .utils import generate_invite_code

logger = logging.getLogger(__name__)


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

    invite_code = generate_invite_code()
    cur.execute("INSERT INTO couples (invite_code) VALUES (%s) RETURNING id", (invite_code,))
    couple_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("foreroo965@gmail.com", "$2b$12$ePVXcjHHhzQ8rGJJsgRdYOj8VAC/EA5KziO40pUGQ0VkjdDNIe1gK", "Aru", couple_id, 247795192),
    )
    aru_id = cur.fetchone()[0]

    cur.execute(
        """INSERT INTO users (email, password_hash, display_name, couple_id, chat_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("moncava8@gmail.com", "$2b$12$ePVXcjHHhzQ8rGJJsgRdYOj8VAC/EA5KziO40pUGQ0VkjdDNIe1gK", "Mon", couple_id, 1560352087),
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
            cur.execute(CREATE_COUPLES)
            # 2. users — depends on couples
            cur.execute(CREATE_USERS)
            # 3. couple_settings — depends on couples + users
            cur.execute(CREATE_COUPLE_SETTINGS)
            # 4. expenses — depends on couples (via couple_id)
            cur.execute(CREATE_EXPENSES)
            # 5. incomes — depends on users (via user_id)
            cur.execute(CREATE_INCOMES)
            # 6. migrations
            cur.execute(ADD_COUPLE_ID_TO_EXPENSES)
            cur.execute(ADD_LEFT_AT_TO_COUPLE_SETTINGS)
            cur.execute(DROP_OLD_EXPENSE_COLUMNS)
            cur.execute(MIGRATE_USERS_STATUS)
            cur.execute(ADD_UPDATE_ID_TO_EXPENSES)
            cur.execute(ADD_UPDATE_ID_TO_INCOMES)

            _seed_default_couple(cur)
        conn.commit()
    logger.info("Database initialised")
