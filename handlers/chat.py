import logging
import random
import re
from telegram import Update
from telegram.ext import ContextTypes
import llm
import database

logger = logging.getLogger(__name__)

_GREETING_PATTERNS = re.compile(
    r"^(hola|buenas|buenos\s*d[ií]as|buenas\s*tardes|buenas\s*noches|"
    r"hey|qu[eé]\s*tal|qu[eé]\s*hubo|qu[eé]\s*onda|holi|hello|hi|"
    r"saludos|qu[eé]\s*hay|q\s*tal|ey|bien\??)\s*[!?.]*$",
    re.IGNORECASE,
)

_GREETING_REPLIES = [
    "¡Hola {sender}! ¿Qué tal? Si necesitas registrar un gasto o ver el balance, aquí estoy. 😊",
    "¡Hey {sender}! ¿En qué te puedo ayudar hoy? Puedo registrar gastos o mostrarte el balance.",
    "¡Buenas, {sender}! ¿Todo bien? Dime si quieres registrar algo o consultar tus finanzas.",
    "¡Hola {sender}! Listo para ayudarte con los gastos. ¿Qué necesitas?",
    "¡Hey {sender}! Aquí estoy. Puedo registrar gastos, ver el balance o ajustar el split. ¿Qué hacemos?",
    "¡Hola {sender}! ¿Me cuentas? Si es un gasto, manda el concepto y el valor.",
]


def _is_greeting(text: str) -> bool:
    cleaned = text.strip()
    return bool(_GREETING_PATTERNS.match(cleaned))


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    sender = user["display_name"]

    if _is_greeting(text):
        reply = random.choice(_GREETING_REPLIES).format(sender=sender)
        await msg.reply_text(reply)
        return

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []
    user_names = tuple(u["display_name"] for u in couple_users) if len(couple_users) == 2 else ("Usuario1", "Usuario2")

    try:
        reply = llm.chat_reply(text, sender, user_names)
        await msg.reply_text(reply)
    except Exception:
        logger.exception("chat_reply LLM call failed")
        await msg.reply_text(
            "¡Hola! Si necesitas registrar un gasto, envía el concepto y el valor. "
            "Para ver el balance, escribe 'Balance'."
        )
