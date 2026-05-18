import logging
from telegram import Update
from telegram.ext import ContextTypes
import llm
import finance
import database

logger = logging.getLogger(__name__)

_NO_DATA_MSG = "No hay gastos registrados para ese mes."


def _fmt(amount: float) -> str:
    return f"${amount:,.0f}"


def _build_summary(bal: dict, users: dict[int, str]) -> str:
    shared = bal["compartido"]
    personal = bal["personal"]

    lines = [
        f"📊 Resumen de Gastos — {bal['mes']} 📊",
        "",
        "🏠 Compartidos:",
    ]

    for uid, amount in shared["gastos_por_usuario"].items():
        name = users.get(uid, f"Usuario {uid}")
        lines.append(f"  {name} pagó: {_fmt(amount)}")

    lines.append(f"  Total:     {_fmt(shared['gastos_totales'])}")
    lines.append("")
    lines.append(f"  ⚖️ {shared['balance_key']}: {_fmt(shared['deuda_total'])}")

    shared_cats = shared["por_categoria"]
    has_shared_cats = any(v > 0 for v in shared_cats.values())
    if has_shared_cats:
        lines.append("")
        lines.append("  📂 Categorías:")
        for cat, val in shared_cats.items():
            if val > 0:
                lines.append(f"    {cat}: {_fmt(val)}")

    viewer_name = personal.get("viewer_name", "")
    lines.append("")
    lines.append(f"👤 Tus gastos personales ({viewer_name}):")
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
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    sender = user["display_name"]

    if year is None or month is None:
        text = msg.text or ""
        date_str = msg.date.strftime("%Y-%m-%d")
        year, month = llm.extract_month(text, date_str)

    expenses = database.get_expenses_by_month(year, month)

    if not expenses:
        await msg.reply_text(_NO_DATA_MSG)
        return

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []
    users_dict = {u["id"]: u["display_name"] for u in couple_users}

    bal = finance.compute_balance(expenses, viewer_id=user["id"], users=users_dict)
    summary = _build_summary(bal, users_dict)
    await msg.reply_text(summary)
