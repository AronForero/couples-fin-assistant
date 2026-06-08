import logging
from telegram import Update
from telegram.ext import ContextTypes
import llm
import database

logger = logging.getLogger(__name__)

_HELP_MSG = (
    "Para eliminar un gasto o ingreso, indica el ID.\n"
    "Ej: \"eliminar gasto 42\"\n"
    "Ej: \"borrar ingreso 7\"\n"
    "\n"
    "Para ver los IDs, escribe \"últimos gastos\" o /last."
)


async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    delete_data = llm.parse_delete(text, sender, date_str)
    if delete_data is None or "id" not in delete_data:
        await msg.reply_text(_HELP_MSG)
        return

    target_id = delete_data["id"]

    expense = database.get_expense_by_id(target_id)
    if expense is not None:
        if expense.get("couple_id") != user.get("couple_id"):
            await msg.reply_text("Este gasto no pertenece a tu pareja actual.")
            return

        database.delete_expense(target_id)

        concepto = expense.get("concepto", "")
        valor = int(expense["valor"])
        fecha = str(expense["fecha"])

        await msg.reply_text(
            f"🗑 Gasto #{target_id} eliminado: {concepto} — ${valor:,}"
        )

        if expense.get("compartida") == "Si":
            partner = database.get_partner(user["id"])
            if partner and partner.get("chat_id"):
                try:
                    await context.bot.send_message(
                        chat_id=partner["chat_id"],
                        text=(
                            f"⚠️ {sender} ha eliminado un gasto compartido:\n"
                            f"#{target_id} — {concepto} — ${valor:,} ({fecha})"
                        ),
                    )
                except Exception:
                    logger.warning("Could not notify partner %s of delete", partner["chat_id"])
        return

    income = database.get_income_by_id(target_id)
    if income is not None:
        if income.get("user_id") != user.get("id"):
            await msg.reply_text("Este ingreso no te pertenece.")
            return

        database.delete_income(target_id)

        concepto = income.get("concepto", "")
        valor = int(income["valor"])
        fecha = str(income["fecha"])

        await msg.reply_text(
            f"🗑 Ingreso #{target_id} eliminado: {concepto} — ${valor:,}"
        )
        return

    await msg.reply_text(f"#{target_id} no encontrado como gasto ni como ingreso.")
