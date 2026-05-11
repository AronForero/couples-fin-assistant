import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, USER_MAP, get_partner_chat_id
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
    "💸 Valor a pagar: ${valor_a_pagar:,.0f}\n"
    "📌 Observación: {observacion}"
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
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    text = msg.text or ""
    date_str = msg.date.strftime("%Y-%m-%d")
    first_name = msg.chat.first_name or ""
    sender = USER_MAP.get(first_name.lower(), first_name)

    edit_data = llm.parse_edit(text, sender, date_str)
    if edit_data is None or "id" not in edit_data:
        await msg.reply_text(_HELP_MSG)
        return

    expense_id = edit_data["id"]
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        await msg.reply_text(f"Gasto #{expense_id} no encontrado.")
        return

    fields_to_update = {k: v for k, v in edit_data.items() if k in _EDITABLE_FIELDS and k != "id"}
    if not fields_to_update:
        await msg.reply_text(
            f"Gasto #{expense_id} encontrado. ¿Qué quieres cambiar?\n"
            f"Campos editables: valor, concepto, fecha, compartida, quien_pago, categoria, subcategoria"
        )
        return

    merged = dict(existing)
    merged.update(fields_to_update)

    needs_split_recompute = {"valor", "compartida", "quien_pago"} & set(fields_to_update.keys())
    if needs_split_recompute:
        split_aru, split_mon = database.get_split()
        merged = finance.compute_split(merged, split_aru, split_mon)
        fields_to_update["valor_a_pagar"] = merged["valor_a_pagar"]
        fields_to_update["observacion"] = merged["observacion"]

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
        partner_id = get_partner_chat_id(sender)
        if partner_id:
            diff = _build_diff(
                {k: existing.get(k) for k in _EDITABLE_FIELDS},
                {k: merged.get(k, existing.get(k)) for k in _EDITABLE_FIELDS},
                set(fields_to_update.keys()) & _EDITABLE_FIELDS,
            )
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"⚠️ {sender} ha editado un gasto compartido #{expense_id}:\n"
                        f"{diff}"
                    ),
                )
            except Exception:
                logger.warning("Could not notify partner %s of edit", partner_id)
