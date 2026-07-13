import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
import llm
import database

logger = logging.getLogger(__name__)

_ERROR_MSG = (
    "Para registrar una deuda, indicá a quién le debés y el monto.\n"
    "Ej: 'Debo 30000 a Moni por gasolina'\n"
    "Ej: 'Moni me debe 50000 por el cine'\n"
    "Ej: 'Le presté 20000 a Moni'"
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

_DELAYED_THRESHOLD_SECONDS = 300  # 5 minutes


def _delayed_note(update: Update) -> str:
    msg_date = update.message.date
    if msg_date.tzinfo is None:
        msg_date = msg_date.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - msg_date).total_seconds()
    if delta > _DELAYED_THRESHOLD_SECONDS:
        sent_str = msg_date.strftime("%d/%m a las %H:%M")
        return f"⏱️ Registrado con retraso (enviado el {sent_str})\n\n"
    return ""


async def handle_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if not database.is_user_active(user):
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    if not user.get("couple_id"):
        await msg.reply_text(
            "No tenés pareja. Las deudas son entre miembros de una pareja."
        )
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    sender = user["display_name"]

    couple_users = database.get_couple_users(user["couple_id"])
    if len(couple_users) < 2:
        await msg.reply_text(
            "Tu pareja aún no se unió. No podés registrar deudas."
        )
        return

    user_names = tuple(u["display_name"] for u in couple_users)

    debt = llm.parse_debt(text, sender, date_str, user_names)
    if debt is None:
        logger.info("parse_debt returned None for: %r", text)
        await msg.reply_text(_ERROR_MSG)
        return

    deudor_name = debt.get("deudor", "")
    acreedor_name = debt.get("acreedor", "")

    deudor_user = next((u for u in couple_users if u["display_name"] == deudor_name), None)
    acreedor_user = next((u for u in couple_users if u["display_name"] == acreedor_name), None)

    if not deudor_user or not acreedor_user:
        logger.warning(
            "Could not resolve deudor=%s or acreedor=%s against couple users %s",
            deudor_name, acreedor_name, user_names,
        )
        await msg.reply_text("No pude identificar a quién le debés. Usá el nombre de tu pareja.")
        return

    expense = {
        "fecha": debt["fecha"],
        "quien_pago": acreedor_name,
        "quien_pago_id": acreedor_user["id"],
        "subcategoria": "Préstamo personal",
        "categoria": "PRÉSTAMO",
        "concepto": debt["concepto"],
        "valor": debt["valor"],
        "compartida": "Si",
        "valor_a_pagar": float(debt["valor"]),
        "debt_user_id": deudor_user["id"],
        "couple_id": user["couple_id"],
        "update_id": update.update_id,
    }

    try:
        expense["id"] = database.insert_expense(expense)
    except Exception:
        logger.exception("DB insert failed for debt")
        await msg.reply_text("Hubo un error al guardar la deuda. Por favor intenta de nuevo.")
        return

    logger.info(
        "debt registered: #%s, deudor=%s, acreedor=%s, valor=%s",
        expense["id"], deudor_name, acreedor_name, expense["valor"],
    )

    confirm = _delayed_note(update) + _CONFIRM_TEMPLATE.format(**expense)

    for u in couple_users:
        if u.get("chat_id"):
            try:
                await context.bot.send_message(chat_id=u["chat_id"], text=confirm)
            except Exception:
                logger.warning("Could not send confirmation to %s", u["chat_id"])
