import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
import llm
import database

logger = logging.getLogger(__name__)

_ERROR_MSG = (
    "Para registrar un ingreso, envialo con un monto. "
    "Ej: 'Salario 2000000' o 'Ingreso freelance 1500000'."
)

_CONFIRM_TEMPLATE = (
    "✅ Ingreso #{id} registrado:\n"
    "📅 Fecha: {fecha}\n"
    "👤 Recibido por: {quien_recibio}\n"
    "📝 Concepto: {concepto}\n"
    "💰 Valor: ${valor:,}"
)

_DELAYED_THRESHOLD_SECONDS = 300  # 5 minutes


def _delayed_note(update: Update) -> str:
    """Return a prefix line if the message was sent more than 5 minutes ago."""
    msg_date = update.message.date
    if msg_date.tzinfo is None:
        msg_date = msg_date.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - msg_date).total_seconds()
    if delta > _DELAYED_THRESHOLD_SECONDS:
        sent_str = msg_date.strftime("%d/%m a las %H:%M")
        return f"⏱️ Registrado con retraso (enviado el {sent_str})\n\n"
    return ""


async def handle_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if not database.is_user_active(user):
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    sender = user["display_name"]

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []
    user_names = tuple(u["display_name"] for u in couple_users) if len(couple_users) == 2 else (sender, "Pareja")

    income = llm.parse_income(text, sender, date_str, user_names)
    if income is None:
        await msg.reply_text(_ERROR_MSG)
        return

    income["user_id"] = user["id"]
    income["update_id"] = update.update_id

    try:
        income["id"] = database.insert_income(income)
    except Exception:
        logger.exception("DB insert failed for income")
        await msg.reply_text("Hubo un error al guardar el ingreso. Por favor intenta de nuevo.")
        return

    confirm = _delayed_note(update) + _CONFIRM_TEMPLATE.format(**income)
    await msg.reply_text(confirm)
