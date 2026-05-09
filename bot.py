import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_TOKEN, ALLOWED_USER_IDS, USER_MAP
import database
import llm
from handlers.expense import handle_expense
from handlers.balance import handle_balance
from handlers.settings import handle_split_command, apply_split
from handlers.chat import handle_chat
from handlers.token import handle_token

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_WELCOME = (
    "👋 Hola! Soy el bot de finanzas de Aru & Mon.\n\n"
    "Puedes escribirme de forma natural:\n"
    "• *Registrar un gasto:* 'cine 30000' o 'Mon pagó supermercado 50000'\n"
    "• *Ver el balance:* 'Balance' o 'Balance de marzo'\n"
    "• *Cambiar el porcentaje:* 'Cambia el split a 65 para Aru y 35 para Mon'\n"
    "• O usa el comando */split 65 35* si prefieres"
)

_SPLIT_UNCLEAR_MSG = (
    "No entendí bien los porcentajes. "
    "Intenta con algo como 'el split es 65 para Aru y 35 para Mon', "
    "o usa el comando /split 65 35."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat.id not in ALLOWED_USER_IDS:
        return
    await update.message.reply_text(_WELCOME, parse_mode="Markdown")


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    first_name = msg.chat.first_name or ""
    sender = USER_MAP.get(first_name.lower(), first_name)

    classified = llm.classify_intent(text, sender, date_str)
    intent = classified["intent"]
    params = classified.get("params", {})

    if intent == "balance":
        await handle_balance(
            update, context,
            year=params.get("year"),
            month=params.get("month"),
        )

    elif intent == "split_change":
        pct_aru = params.get("split_aru")
        pct_mon = params.get("split_mon")
        if pct_aru is None or pct_mon is None:
            await msg.reply_text(_SPLIT_UNCLEAR_MSG)
        else:
            await apply_split(update, context, float(pct_aru), float(pct_mon))

    elif intent == "chat":
        await handle_chat(update, context)

    else:
        await handle_expense(update, context)


def main() -> None:
    database.init_db()
    logger.info("Database initialised")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("split", handle_split_command))
    app.add_handler(CommandHandler("token", handle_token))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch))

    logger.info("Bot starting (polling)…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
