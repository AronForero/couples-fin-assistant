import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, USER_MAP, get_partner_chat_id
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
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    first_name = msg.chat.first_name or ""
    sender = USER_MAP.get(first_name.lower(), first_name)

    delete_data = llm.parse_delete(text, sender, date_str)
    if delete_data is None or "id" not in delete_data:
        await msg.reply_text(_HELP_MSG)
        return

    expense_id = delete_data["id"]
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        await msg.reply_text(f"Gasto #{expense_id} no encontrado.")
        return

    database.delete_expense(expense_id)

    concepto = existing.get("concepto", "")
    valor = int(existing["valor"])
    payer = existing["quien_pago"]
    fecha = str(existing["fecha"])
    compartida = existing.get("compartida", "No")

    await msg.reply_text(
        f"🗑 Gasto #{expense_id} eliminado: {concepto} — ${valor:,}"
    )

    if compartida == "Si":
        partner_id = get_partner_chat_id(sender)
        if partner_id:
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"⚠️ {sender} ha eliminado un gasto compartido:\n"
                        f"#{expense_id} — {concepto} — ${valor:,} ({payer}, {fecha})"
                    ),
                )
            except Exception:
                logger.warning("Could not notify partner %s of delete", partner_id)
