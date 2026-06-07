import logging
from telegram import Update
from telegram.ext import ContextTypes
import llm
import database

logger = logging.getLogger(__name__)

_HELP_MSG = (
    "Para eliminar un gasto, indica el ID.\n"
    "Ej: \"eliminar gasto 42\"\n"
    "\n"
    "Para ver los IDs, escribe \"últimos gastos\" o /last."
)


async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    # Solo user guard
    if not user.get("couple_id"):
        await msg.reply_text("No tenés pareja. Creá una desde la web.")
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    sender = user["display_name"]

    delete_data = llm.parse_delete(text, sender, date_str)
    if delete_data is None or "id" not in delete_data:
        await msg.reply_text(_HELP_MSG)
        return

    expense_id = delete_data["id"]
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        await msg.reply_text(f"Gasto #{expense_id} no encontrado.")
        return

    # Verify expense belongs to user's active couple
    if existing.get("couple_id") != user.get("couple_id"):
        await msg.reply_text("Este gasto no pertenece a tu pareja actual.")
        return

    database.delete_expense(expense_id)

    concepto = existing.get("concepto", "")
    valor = int(existing["valor"])
    fecha = str(existing["fecha"])

    await msg.reply_text(
        f"🗑 Gasto #{expense_id} eliminado: {concepto} — ${valor:,}"
    )

    if existing.get("compartida") == "Si":
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            try:
                await context.bot.send_message(
                    chat_id=partner["chat_id"],
                    text=(
                        f"⚠️ {sender} ha eliminado un gasto compartido:\n"
                        f"#{expense_id} — {concepto} — ${valor:,} ({fecha})"
                    ),
                )
            except Exception:
                logger.warning("Could not notify partner %s of delete", partner["chat_id"])
