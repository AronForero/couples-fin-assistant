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


async def handle_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_id: int | None = None,
) -> None:
    msg = update.message

    # text/date_str are only used by the parse_delete fallback (when
    # classify_intent didn't extract an id).  sender is always needed
    # for the partner-notification message further down.
    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")

    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    sender = user["display_name"]

    logger.info(
        "delete request from %s (chat_id=%s): %r",
        sender,
        msg.chat.id,
        text,
    )

    if not database.is_user_active(user):
        logger.info("user %s suspended, ignoring delete", sender)
        await msg.reply_text(
            "Tu cuenta está suspendida. Completa tu pago para continuar."
        )
        return

    # ── Extract target_id ────────────────────────────────────────────
    # Prefer the id already extracted by classify_intent (no extra LLM call).
    # Fall back to parse_delete only if the dispatcher didn't pass one.
    if target_id is None:
        delete_data = llm.parse_delete(text, sender, date_str)
        if delete_data is None or "id" not in delete_data:
            logger.info("no id found in message: %r", text)
            await msg.reply_text(_HELP_MSG)
            return
        target_id = delete_data["id"]
        logger.info("id=%s extracted via parse_delete fallback", target_id)
    else:
        logger.info(
            "using id=%s from classify_intent (skipping parse_delete)",
            target_id,
        )

    # ── Expense branch ────────────────────────────────────────────────
    expense = database.get_expense_by_id(target_id)
    if expense is not None:
        logger.info(
            "expense #%s found, couple_id=%s, compartida=%s",
            target_id,
            expense.get("couple_id"),
            expense.get("compartida"),
        )

        if expense.get("couple_id") != user.get("couple_id"):
            logger.info(
                "expense #%s belongs to couple_id=%s, user is in couple_id=%s",
                target_id,
                expense.get("couple_id"),
                user.get("couple_id"),
            )
            await msg.reply_text("Este gasto no pertenece a tu pareja actual.")
            return

        # Personal expenses can only be deleted by the original payer.
        # Shared expenses can be deleted by either member.
        if expense.get("compartida") == "No" and expense.get("quien_pago_id") != user.get("id"):
            logger.info(
                "delete rejected: expense #%s is personal, paid by user_id=%s, requester is user_id=%s",
                target_id,
                expense.get("quien_pago_id"),
                user.get("id"),
            )
            await msg.reply_text("Solo quien pagó puede eliminar este gasto personal.")
            return

        deleted = database.delete_expense(target_id)
        if not deleted:
            logger.warning(
                "delete_expense returned False for id=%s (0 rows affected)",
                target_id,
            )
            await msg.reply_text(
                f"No se pudo eliminar el gasto #{target_id} "
                "(¿ya fue borrado?). Intentalo de nuevo."
            )
            return

        logger.info("expense #%s deleted by %s", target_id, sender)

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
                    logger.warning(
                        "Could not notify partner %s of delete",
                        partner["chat_id"],
                    )
        return

    # ── Income branch ─────────────────────────────────────────────────
    income = database.get_income_by_id(target_id)
    if income is not None:
        logger.info(
            "income #%s found, user_id=%s",
            target_id,
            income.get("user_id"),
        )

        if income.get("user_id") != user.get("id"):
            logger.info(
                "income #%s belongs to user_id=%s, requester is user_id=%s",
                target_id,
                income.get("user_id"),
                user.get("id"),
            )
            await msg.reply_text("Este ingreso no te pertenece.")
            return

        deleted = database.delete_income(target_id)
        if not deleted:
            logger.warning(
                "delete_income returned False for id=%s (0 rows affected)",
                target_id,
            )
            await msg.reply_text(
                f"No se pudo eliminar el ingreso #{target_id} "
                "(¿ya fue borrado?). Intentalo de nuevo."
            )
            return

        logger.info("income #%s deleted by %s", target_id, sender)

        concepto = income.get("concepto", "")
        valor = int(income["valor"])
        fecha = str(income["fecha"])

        await msg.reply_text(
            f"🗑 Ingreso #{target_id} eliminado: {concepto} — ${valor:,}"
        )
        return

    # ── Not found ─────────────────────────────────────────────────────
    logger.info("id=%s not found as expense or income", target_id)
    await msg.reply_text(f"#{target_id} no encontrado como gasto ni como ingreso.")