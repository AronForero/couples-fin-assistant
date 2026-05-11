import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, USER_MAP
import llm
import finance
import database

logger = logging.getLogger(__name__)

_ERROR_MSG = (
    "Hola. Para registrar un gasto, envía el concepto y el valor "
    "(ej. 'cine 30000'). Si quieres ver el balance, escribe 'Balance'."
)

_CONFIRM_TEMPLATE = (
    "✅ Gasto #{id} registrado:\n"
    "📅 Fecha: {fecha}\n"
    "👤 Quien pagó: {quien_pago}\n"
    "🏷 SubCategoría: {subcategoria}\n"
    "📂 Categoría: {categoria}\n"
    "📝 Concepto: {concepto}\n"
    "💰 Valor: ${valor:,}\n"
    "🤝 Compartida: {compartida}\n"
    "💸 Valor a pagar: ${valor_a_pagar:,.0f}\n"
    "📌 Observación: {observacion}"
)


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_id = msg.chat.id

    if user_id not in ALLOWED_USER_IDS:
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    first_name = msg.chat.first_name or ""
    sender = USER_MAP.get(first_name.lower(), first_name)

    expense = llm.parse_expense(text, sender, date_str)
    if expense is None:
        await msg.reply_text(_ERROR_MSG)
        return

    split_aru, split_mon = database.get_split()
    expense = finance.compute_split(expense, split_aru, split_mon)

    try:
        expense["id"] = database.insert_expense(expense)
    except Exception:
        logger.exception("DB insert failed")
        await msg.reply_text("Hubo un error al guardar el gasto. Por favor intenta de nuevo.")
        return

    confirm = _CONFIRM_TEMPLATE.format(**expense)
    for uid in ALLOWED_USER_IDS:
        try:
            await context.bot.send_message(chat_id=uid, text=confirm)
        except Exception:
            logger.warning("Could not send confirmation to %s", uid)
