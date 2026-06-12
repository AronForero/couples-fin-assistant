import calendar
import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

import database
import finance
from config import MONTH_NAMES_ES

logger = logging.getLogger(__name__)


def _resolve_period(year: int | None, month: int | None) -> tuple[str, str, str]:
    """Return (start_iso, end_iso, human_label) for the given year/month.

    year/month None → current month. year given, month None → whole year.
    """
    today = date.today()
    if year and month:
        first = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        start = first.isoformat()
        end = date(year, month, last_day).isoformat()
        label = f"{MONTH_NAMES_ES.get(month, '')} {year}"
    elif year:
        start = date(year, 1, 1).isoformat()
        end = date(year, 12, 31).isoformat()
        label = f"Año {year}"
    else:
        start = today.replace(day=1).isoformat()
        end = today.isoformat()
        label = f"{MONTH_NAMES_ES.get(today.month, '')} {today.year}"
    return start, end, label


async def handle_actual_money(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    year: int | None = None,
    month: int | None = None,
) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if not database.is_user_active(user):
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    start, end, label = _resolve_period(year, month)

    incomes = database.get_incomes_by_date_range(user["id"], start, end)

    splits = None
    if user.get("couple_id"):
        expenses = database.get_expenses_by_date_range(user["couple_id"], start, end)
        splits = database.get_split_for_couple(user["couple_id"])
    else:
        expenses = []

    result = finance.compute_actual_money(user, incomes, expenses, splits)

    actual = result["actual_money"]
    indicator = "🟢" if actual >= 0 else "🔴"
    remaining_label = "Te quedan" if actual >= 0 else "Estás en negativo por"

    lines = [
        f"💰 Tu dinero real — {label}",
        "",
        f"💵 Ingresos:           ${result['total_income']:,}",
        f"💸 Gastos personales:  ${result['personal_expenses']:,}",
    ]

    if user.get("couple_id") and splits:
        pct = int(round(result["split_percentage"] * 100))
        lines.append(
            f"🤝 Tu parte de compartidos ({pct}%): ${result['shared_expenses_my_share']:,}"
        )
        lines.append(
            f"   (Total gastos compartidos: ${result['shared_expenses_total']:,})"
        )

    lines += [
        "",
        f"{indicator} {remaining_label}: ${abs(actual):,}",
    ]

    await msg.reply_text("\n".join(lines))
