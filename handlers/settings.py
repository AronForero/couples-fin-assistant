import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, USER_MAP
import database

logger = logging.getLogger(__name__)

_USAGE_MSG = "Uso: /split <% Aru> <% Mon>  — ej. /split 65 35"
_SUM_ERROR_MSG = "Los porcentajes deben sumar 100. Ej: /split 65 35"


async def apply_split(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pct_aru: float,
    pct_mon: float,
) -> None:
    """Persist a new split and notify both users. Called from both /split and conversational dispatch."""
    msg = update.message
    sender_id = msg.chat.id

    if abs(pct_aru + pct_mon - 100) > 0.1:
        await msg.reply_text(_SUM_ERROR_MSG)
        return

    split_aru = round(pct_aru / 100, 6)
    split_mon = round(pct_mon / 100, 6)

    database.set_setting("split_aru", str(split_aru))
    database.set_setting("split_mon", str(split_mon))

    first_name = msg.chat.first_name or ""
    sender_label = USER_MAP.get(first_name.lower(), first_name)

    confirm = (
        f"✅ Porcentaje actualizado:\n"
        f"Aru: {pct_aru:.4g}% · Mon: {pct_mon:.4g}%\n"
        f"Aplica a los gastos nuevos a partir de ahora."
    )
    await msg.reply_text(confirm)

    notification = (
        f"⚠️ {sender_label} cambió el porcentaje de gastos compartidos:\n"
        f"Aru: {pct_aru:.4g}% · Mon: {pct_mon:.4g}%\n"
        f"Aplica a los gastos nuevos a partir de ahora."
    )
    other_ids = ALLOWED_USER_IDS - {sender_id}
    for uid in other_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=notification)
        except Exception:
            logger.warning("Could not notify user %s of split change", uid)


async def handle_split_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/split command — kept as a convenience for explicit syntax."""
    msg = update.message
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    args = context.args or []
    if len(args) != 2:
        await msg.reply_text(_USAGE_MSG)
        return

    try:
        pct_aru = float(args[0])
        pct_mon = float(args[1])
    except ValueError:
        await msg.reply_text(_USAGE_MSG)
        return

    await apply_split(update, context, pct_aru, pct_mon)
