import logging
from telegram import Update
from telegram.ext import ContextTypes
import llm
import finance
import database

logger = logging.getLogger(__name__)

_EDITABLE_FIELDS = {"valor", "concepto", "fecha", "compartida", "quien_pago", "categoria", "subcategoria"}

_HELP_MSG = (
    "Para editar un gasto, indica el ID y los campos a cambiar.\n"
    "Ej: \"editar gasto 42, era compartido\"\n"
    "Ej: \"gasto 42, el valor era 25000\"\n"
    "\n"
    "Para ver los IDs, escribe \"últimos gastos\" o /last."
)

_EDIT_CONFIRM_TEMPLATE = (
    "✏️ Gasto #{id} actualizado:\n"
    "📅 Fecha: {fecha}\n"
    "👤 Quien pagó: {quien_pago}\n"
    "🏷 SubCategoría: {subcategoria}\n"
    "📂 Categoría: {categoria}\n"
    "📝 Concepto: {concepto}\n"
    "💰 Valor: ${valor:,}\n"
    "🤝 Compartida: {compartida}\n"
    "💸 Valor a pagar: ${valor_a_pagar:,.0f}"
)

_FIELD_LABELS = {
    "fecha": "📅 Fecha",
    "quien_pago": "👤 Quien pagó",
    "subcategoria": "🏷 SubCategoría",
    "categoria": "📂 Categoría",
    "concepto": "📝 Concepto",
    "valor": "💰 Valor",
    "compartida": "🤝 Compartida",
}


def _fmt_val(field: str, val) -> str:
    if field == "valor":
        return f"${int(val):,}"
    return str(val)


def _build_diff(before: dict, after: dict, changed_keys: set[str]) -> str:
    lines = []
    for key in changed_keys:
        label = _FIELD_LABELS.get(key, key)
        old_val = _fmt_val(key, before.get(key, ""))
        new_val = _fmt_val(key, after.get(key, ""))
        lines.append(f"{label}: {old_val} → {new_val}")
    return "\n".join(lines)


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    couple_users = database.get_couple_users(user["couple_id"])
    user_names = tuple(u["display_name"] for u in couple_users) if len(couple_users) == 2 else ("Usuario1", "Usuario2")

    edit_data = llm.parse_edit(text, sender, date_str, user_names)
    if edit_data is None or "id" not in edit_data:
        await msg.reply_text(_HELP_MSG)
        return

    expense_id = edit_data["id"]
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        await msg.reply_text(f"Gasto #{expense_id} no encontrado.")
        return

    # Verify expense belongs to user's active couple
    if existing.get("couple_id") != user.get("couple_id"):
        await msg.reply_text("Este gasto no pertenece a tu pareja actual.")
        return

    fields_to_update = {k: v for k, v in edit_data.items() if k in _EDITABLE_FIELDS and k != "id"}
    if not fields_to_update:
        await msg.reply_text(
            f"Gasto #{expense_id} encontrado. ¿Qué quieres cambiar?\n"
            f"Campos editables: valor, concepto, fecha, compartida, quien_pago, categoria, subcategoria"
        )
        return

    # Solo user trying to mark expense as shared
    if fields_to_update.get("compartida") == "Si" and len(couple_users) < 2:
        await msg.reply_text(
            "No podés marcar un gasto como compartido sin una pareja. Usá la opción Invitar en la página web."
        )
        return

    if "quien_pago" in fields_to_update:
        payer_name = fields_to_update["quien_pago"]
        payer_user = next((u for u in couple_users if u["display_name"] == payer_name), None)
        if payer_user:
            fields_to_update["quien_pago_id"] = payer_user["id"]

    merged = dict(existing)
    merged.update(fields_to_update)

    needs_split_recompute = {"valor", "compartida", "quien_pago"} & set(fields_to_update.keys())
    if needs_split_recompute:
        splits = database.get_split_for_couple(user["couple_id"])
        users_dict = {u["id"]: u["display_name"] for u in couple_users}
        if splits and users_dict:
            merged = finance.compute_split(merged, splits, users_dict)
            fields_to_update["valor_a_pagar"] = merged["valor_a_pagar"]
            if "debt_user_id" in merged:
                fields_to_update["debt_user_id"] = merged["debt_user_id"]

    try:
        database.update_expense(expense_id, fields_to_update)
    except Exception:
        logger.exception("DB update failed for expense %s", expense_id)
        await msg.reply_text("Hubo un error al actualizar el gasto. Intenta de nuevo.")
        return

    updated = database.get_expense_by_id(expense_id)
    if updated:
        updated["valor"] = int(updated["valor"])
        updated["valor_a_pagar"] = float(updated["valor_a_pagar"]) if updated.get("valor_a_pagar") else 0
        confirm = _EDIT_CONFIRM_TEMPLATE.format(**updated)
    else:
        confirm = f"✏️ Gasto #{expense_id} actualizado."

    await msg.reply_text(confirm)

    shared_before = existing.get("compartida", "No") == "Si"
    shared_after = (merged.get("compartida") or existing.get("compartida", "No")) == "Si"
    if shared_before or shared_after:
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            diff = _build_diff(
                {k: existing.get(k) for k in _EDITABLE_FIELDS},
                {k: merged.get(k, existing.get(k)) for k in _EDITABLE_FIELDS},
                set(fields_to_update.keys()) & _EDITABLE_FIELDS,
            )
            try:
                await context.bot.send_message(
                    chat_id=partner["chat_id"],
                    text=(
                        f"⚠️ {sender} ha editado un gasto compartido #{expense_id}:\n"
                        f"{diff}"
                    ),
                )
            except Exception:
                logger.warning("Could not notify partner %s of edit", partner["chat_id"])
