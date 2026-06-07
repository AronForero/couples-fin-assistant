import logging
from telegram import Update
from telegram.ext import ContextTypes
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
    "💸 Valor a pagar: ${valor_a_pagar:,.0f}"
)


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    # Solo user guard
    if not user.get("couple_id"):
        await msg.reply_text(
            "No tenés pareja. Creá una desde la web para registrar gastos compartidos."
        )
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    sender = user["display_name"]

    couple_users = database.get_couple_users(user["couple_id"])
    user_names = tuple(u["display_name"] for u in couple_users) if len(couple_users) == 2 else ("Usuario1", "Usuario2")

    expense = llm.parse_expense(text, sender, date_str, user_names)
    if expense is None:
        await msg.reply_text(_ERROR_MSG)
        return

    # Solo user trying to register a shared expense
    if expense.get("compartida") == "Si" and len(couple_users) < 2:
        await msg.reply_text(
            "Tu pareja aún no se unió. Usá el código en la opción Invitar en la página web para compartir gastos."
        )
        return

    payer_name = expense.get("quien_pago", "")
    payer_user = next((u for u in couple_users if u["display_name"] == payer_name), None)
    if payer_user:
        expense["quien_pago_id"] = payer_user["id"]

    # Add couple_id to expense
    expense["couple_id"] = user["couple_id"]

    splits = database.get_split_for_couple(user["couple_id"])
    users_dict = {u["id"]: u["display_name"] for u in couple_users}

    if splits and users_dict:
        expense = finance.compute_split(expense, splits, users_dict)
    else:
        expense.setdefault("valor_a_pagar", expense["valor"])

    try:
        expense["id"] = database.insert_expense(expense)
    except Exception:
        logger.exception("DB insert failed")
        await msg.reply_text("Hubo un error al guardar el gasto. Por favor intenta de nuevo.")
        return

    confirm = _CONFIRM_TEMPLATE.format(**expense)
    for u in couple_users:
        if u.get("chat_id"):
            try:
                await context.bot.send_message(chat_id=u["chat_id"], text=confirm)
            except Exception:
                logger.warning("Could not send confirmation to %s", u["chat_id"])
