import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_TOKEN
import database
import llm
from handlers.expense import handle_expense
from handlers.income import handle_income
from handlers.balance import handle_balance
from handlers.settings import handle_split_command, apply_split
from handlers.chat import handle_chat
from handlers.recent import handle_recent
from handlers.edit import handle_edit
from handlers.delete import handle_delete
from handlers.link import handle_link
from handlers.actual_money import handle_actual_money

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _get_user_names(couple_users: list[dict]) -> tuple[str, str]:
    names = tuple(u["display_name"] for u in couple_users)
    return names if len(names) == 2 else ("Usuario1", "Usuario2")


async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = database.get_user_by_chat_id(update.message.chat.id)
    if not user:
        return
    args = context.args or []
    limit = None
    if args:
        try:
            limit = int(args[0])
        except ValueError:
            pass
    await handle_recent(update, context, limit=limit)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = database.get_user_by_chat_id(update.message.chat.id)
    if not user:
        await update.message.reply_text(
            "¡Hola! Soy FinDuo, tu asistente de finanzas.\n"
            "Vinculá tu cuenta con /link <email>."
        )
        return

    if user.get("couple_id"):
        couple_users = database.get_couple_users(user["couple_id"])
        user_names = _get_user_names(couple_users)
        welcome = (
            f"👋 ¡Hola {user['display_name']}! Estás en pareja con {user_names[1] if user_names[0] == user['display_name'] else user_names[0]}.\n\n"
            "Puedes escribirme de forma natural:\n"
            "• *Registrar un gasto:* 'cine 30000' o 'Mon pagó supermercado 50000'\n"
            "• *Registrar un ingreso:* 'Salario 2000000' o 'Ingreso freelance 1500000'\n"
            "• *Ver el balance:* 'Balance' o 'Balance de marzo'\n"
            "• *Ver tu dinero real:* '¿Cuánto tengo?' o '¿Cuánto me queda?'\n"
            "• *Cambiar el porcentaje:* 'Cambia el split a 65 para Aru y 35 para Mon'\n"
            "• O usa el comando */split 65 35* si prefieres"
        )
    else:
        welcome = (
            f"¡Hola {user['display_name']}! No estás en una pareja.\n"
            f"Podés registrar gastos personales e ingresos desde acá.\n"
            f"Creá una pareja desde la web para empezar a registrar gastos compartidos."
        )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        await msg.reply_text(
            "No estás registrado. Usa /link <email> para vincular tu cuenta."
        )
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    sender = user["display_name"]
    user_id = user["id"]

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []
    user_names = _get_user_names(couple_users)

    classified = llm.classify_intent(text, sender, date_str, user_names)
    intent = classified["intent"]
    params = classified.get("params", {})

    if intent == "balance":
        await handle_balance(
            update, context,
            year=params.get("year"),
            month=params.get("month"),
        )

    elif intent == "split_change":
        pct_user1 = params.get("split_user1")
        pct_user2 = params.get("split_user2")
        if pct_user1 is None or pct_user2 is None:
            names = user_names
            await msg.reply_text(
                f"No entendí bien los porcentajes. "
                f"Intenta con algo como 'el split es 65 para {names[0]} y 35 para {names[1]}', "
                f"o usa el comando /split 65 35."
            )
        else:
            await apply_split(update, context, float(pct_user1), float(pct_user2))

    elif intent == "chat":
        await handle_chat(update, context)

    elif intent == "recent":
        await handle_recent(update, context, limit=params.get("limit"))

    elif intent == "edit":
        await handle_edit(update, context)

    elif intent == "delete":
        await handle_delete(update, context, target_id=params.get("id"))

    elif intent == "income":
        await handle_income(update, context)

    elif intent == "actual_money":
        await handle_actual_money(
            update, context,
            year=params.get("year"),
            month=params.get("month"),
        )

    else:
        await handle_expense(update, context)


def main() -> None:
    database.init_db()
    logger.info("Database initialised")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", handle_link))
    app.add_handler(CommandHandler("split", handle_split_command))
    app.add_handler(CommandHandler("last", last_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch))

    logger.info("Bot starting (polling)…")
    app.run_polling()


if __name__ == "__main__":
    main()
