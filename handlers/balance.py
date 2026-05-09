import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, USER_MAP
import llm
import finance
import database

logger = logging.getLogger(__name__)

_NO_DATA_MSG = "No hay gastos registrados para ese mes."


def _fmt(amount: float) -> str:
    return f"${amount:,.0f}"


def _build_summary(bal: dict) -> str:
    shared = bal["compartido"]
    personal = bal["personal"]
    viewer = personal["viewer"]

    lines = [
        f"📊 Resumen de Gastos — {bal['mes']} 📊",
        "",
        "🏠 Compartidos:",
        f"  Aron pagó: {_fmt(shared['aron_gasto'])}",
        f"  Mon pagó:  {_fmt(shared['mon_gasto'])}",
        f"  Total:     {_fmt(shared['gastos_totales'])}",
        "",
        f"  ⚖️ {shared['balance_key']}: {_fmt(shared['deuda_total'])}",
    ]

    shared_cats = shared["por_categoria"]
    has_shared_cats = any(v > 0 for v in shared_cats.values())
    if has_shared_cats:
        lines.append("")
        lines.append("  📂 Categorías:")
        for cat, val in shared_cats.items():
            if val > 0:
                lines.append(f"    {cat}: {_fmt(val)}")

    lines.append("")
    lines.append(f"👤 Tus gastos personales ({viewer}):")
    lines.append(f"  Total: {_fmt(personal['viewer_gasto'])}")

    personal_cats = personal["por_categoria"]
    has_personal_cats = any(v > 0 for v in personal_cats.values())
    if has_personal_cats:
        lines.append("")
        lines.append("  📂 Categorías:")
        for cat, val in personal_cats.items():
            if val > 0:
                lines.append(f"    {cat}: {_fmt(val)}")

    return "\n".join(lines)


async def handle_balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    year: int | None = None,
    month: int | None = None,
) -> None:
    msg = update.message
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    first_name = msg.chat.first_name or ""
    sender = USER_MAP.get(first_name.lower(), first_name)

    if year is None or month is None:
        text = msg.text or ""
        date_str = msg.date.strftime("%Y-%m-%d")
        year, month = llm.extract_month(text, date_str)

    expenses = database.get_expenses_by_month(year, month)

    if not expenses:
        await msg.reply_text(_NO_DATA_MSG)
        return

    bal = finance.compute_balance(expenses, viewer=sender)
    summary = _build_summary(bal)
    await msg.reply_text(summary)
