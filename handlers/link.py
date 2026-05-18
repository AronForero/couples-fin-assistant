import logging
from telegram import Update
from telegram.ext import ContextTypes
import database

logger = logging.getLogger(__name__)

_USAGE_MSG = "Uso: /link <email>\nEj: /link aru@finbot.local"
_NOT_FOUND_MSG = "Email no registrado. Regístrate primero en el dashboard."
_ALREADY_LINKED_MSG = "Ese email ya está vinculado a otra cuenta de Telegram."
_SUCCESS_MSG = "✅ Cuenta vinculada. Ya puedes usar el bot."


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = msg.chat.id

    existing = database.get_user_by_chat_id(chat_id)
    if existing:
        await msg.reply_text(f"Ya estás vinculado como {existing['display_name']}.")
        return

    args = context.args or []
    if len(args) != 1:
        await msg.reply_text(_USAGE_MSG)
        return

    email = args[0].strip().lower()
    user = database.get_user_by_email(email)
    if not user:
        await msg.reply_text(_NOT_FOUND_MSG)
        return

    if user.get("chat_id") and user["chat_id"] != chat_id:
        await msg.reply_text(_ALREADY_LINKED_MSG)
        return

    database.update_user_chat_id(user["id"], chat_id)
    logger.info("User %s linked chat_id %s", email, chat_id)
    await msg.reply_text(_SUCCESS_MSG)
