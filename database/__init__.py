"""Database layer — re-exports the public API for backward compatibility.

Internal structure:
    connection.py     get_conn, DSN, module logger
    schema.py         CREATE TABLE DDL + migration SQL
    utils.py          generate_invite_code
    init.py           init_db() orchestration + seed
    users.py          user CRUD + is_user_active + status updates
    couples.py        couple lifecycle (create, join, leave, history)
    couple_settings.py split percentage CRUD
    expenses.py       expense CRUD
    incomes.py        income CRUD
"""

from .connection import get_conn
from .couple_settings import get_split_for_couple, update_split_for_couple
from .couples import (
    create_couple,
    get_couple_by_id,
    get_couple_expenses,
    get_user_couples,
    join_couple,
    leave_couple,
)
from .expenses import (
    delete_expense,
    get_expense_by_id,
    get_expenses_by_month,
    get_expenses_by_month_and_users,
    get_recent_expenses,
    insert_expense,
    update_expense,
)
from .incomes import (
    delete_income,
    get_income_by_id,
    get_incomes_by_month,
    get_recent_incomes,
    insert_income,
    update_income,
)
from .init import init_db
from .users import (
    create_user,
    get_all_chat_ids,
    get_couple_users,
    get_partner,
    get_user_by_chat_id,
    get_user_by_display_name,
    get_user_by_email,
    get_user_by_id,
    is_user_active,
    update_user_chat_id,
    update_user_status,
)
from .utils import generate_invite_code

__all__ = [
    "create_couple",
    "create_user",
    "delete_expense",
    "delete_income",
    "generate_invite_code",
    "get_all_chat_ids",
    "get_conn",
    "get_couple_by_id",
    "get_couple_expenses",
    "get_couple_users",
    "get_expense_by_id",
    "get_expenses_by_month",
    "get_expenses_by_month_and_users",
    "get_income_by_id",
    "get_incomes_by_month",
    "get_partner",
    "get_recent_expenses",
    "get_recent_incomes",
    "get_split_for_couple",
    "get_user_by_chat_id",
    "get_user_by_display_name",
    "get_user_by_email",
    "get_user_by_id",
    "get_user_couples",
    "init_db",
    "insert_expense",
    "insert_income",
    "is_user_active",
    "join_couple",
    "leave_couple",
    "update_expense",
    "update_income",
    "update_split_for_couple",
    "update_user_chat_id",
    "update_user_status",
]
