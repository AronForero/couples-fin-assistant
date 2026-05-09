import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, CHAT_ID_TO_USER
import api_auth

logger = logging.getLogger(__name__)


async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    user = CHAT_ID_TO_USER.get(msg.chat.id)
    if not user:
        await msg.reply_text("No se pudo identificar tu usuario.")
        return

    token = api_auth.create_token(user)
    await msg.reply_text(
        f"🔑 Tu token para el dashboard:\n\n"
        f"`{token}`\n\n"
        f"Cópialo y pégalo en la página de login del dashboard.\n"
        f"El token expira en 30 días.",
        parse_mode="Markdown",
    )
