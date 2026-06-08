import logging
from telegram import Update
from telegram.ext import ContextTypes
import database

logger = logging.getLogger(__name__)

_USAGE_MSG = "Uso: /split <% usuario1> <% usuario2>  — ej. /split 65 35"
_SUM_ERROR_MSG = "Los porcentajes deben sumar 100. Ej: /split 65 35"


async def apply_split(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pct_user1: float,
    pct_user2: float,
) -> None:
    """Persist a new split and notify both users. Called from both /split and conversational dispatch."""
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if not database.is_user_active(user):
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    # Solo user guard
    if not user.get("couple_id"):
        await msg.reply_text("No tenés pareja. Creá una desde la web para configurar el split.")
        return

    if abs(pct_user1 + pct_user2 - 100) > 0.1:
        await msg.reply_text(_SUM_ERROR_MSG)
        return

    couple_users = database.get_couple_users(user["couple_id"])
    if len(couple_users) != 2:
        await msg.reply_text("No se pudo determinar la pareja.")
        return

    splits = {
        couple_users[0]["id"]: round(pct_user1 / 100, 6),
        couple_users[1]["id"]: round(pct_user2 / 100, 6),
    }
    database.update_split_for_couple(user["couple_id"], splits)

    names = [u["display_name"] for u in couple_users]
    confirm = (
        f"✅ Porcentaje actualizado:\n"
        f"{names[0]}: {pct_user1:.4g}% · {names[1]}: {pct_user2:.4g}%\n"
        f"Aplica a los gastos nuevos a partir de ahora."
    )
    await msg.reply_text(confirm)

    partner = database.get_partner(user["id"])
    if partner and partner.get("chat_id") and partner["chat_id"] != msg.chat.id:
        notification = (
            f"⚠️ {user['display_name']} cambió el porcentaje de gastos compartidos:\n"
            f"{names[0]}: {pct_user1:.4g}% · {names[1]}: {pct_user2:.4g}%\n"
            f"Aplica a los gastos nuevos a partir de ahora."
        )
        try:
            await context.bot.send_message(chat_id=partner["chat_id"], text=notification)
        except Exception:
            logger.warning("Could not notify partner %s of split change", partner["chat_id"])


async def handle_split_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/split command — kept as a convenience for explicit syntax."""
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if not database.is_user_active(user):
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    args = context.args or []
    if len(args) != 2:
        await msg.reply_text(_USAGE_MSG)
        return

    try:
        pct_user1 = float(args[0])
        pct_user2 = float(args[1])
    except ValueError:
        await msg.reply_text(_USAGE_MSG)
        return

    await apply_split(update, context, pct_user1, pct_user2)
