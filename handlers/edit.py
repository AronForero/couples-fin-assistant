import logging
from telegram import Update
from telegram.ext import ContextTypes
import llm
import finance
import database

logger = logging.getLogger(__name__)

_EXPENSE_EDITABLE_FIELDS = {"valor", "concepto", "fecha", "compartida", "quien_pago", "categoria", "subcategoria"}
_INCOME_EDITABLE_FIELDS = {"valor", "concepto", "fecha"}

_HELP_MSG = (
    "Para editar un gasto o ingreso, indica el ID y los campos a cambiar.\n"
    "Ej: \"editar gasto 42, era compartido\"\n"
    "Ej: \"gasto 42, el valor era 25000\"\n"
    "Ej: \"ingreso 7, el valor era 2500000\"\n"
    "\n"
    "Para ver los IDs, escribe \"últimos gastos\" o /last."
)

_EDIT_EXPENSE_TEMPLATE = (
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

_EDIT_INCOME_TEMPLATE = (
    "✏️ Ingreso #{id} actualizado:\n"
    "📅 Fecha: {fecha}\n"
    "📝 Concepto: {concepto}\n"
    "💰 Valor: ${valor:,}"
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


async def _edit_expense(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: dict,
    expense_id: int,
    edit_data: dict,
) -> None:
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        await update.message.reply_text(f"Gasto #{expense_id} no encontrado.")
        return

    if existing.get("couple_id") != user.get("couple_id"):
        await update.message.reply_text("Este gasto no pertenece a tu pareja actual.")
        return

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []

    fields_to_update = {k: v for k, v in edit_data.items() if k in _EXPENSE_EDITABLE_FIELDS and k != "id"}
    if not fields_to_update:
        await update.message.reply_text(
            f"Gasto #{expense_id} encontrado. ¿Qué quieres cambiar?\n"
            f"Campos editables: valor, concepto, fecha, compartida, quien_pago, categoria, subcategoria"
        )
        return

    if fields_to_update.get("compartida") == "Si" and len(couple_users) < 2:
        await update.message.reply_text(
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
        await update.message.reply_text("Hubo un error al actualizar el gasto. Intenta de nuevo.")
        return

    updated = database.get_expense_by_id(expense_id)
    if updated:
        updated["valor"] = int(updated["valor"])
        updated["valor_a_pagar"] = float(updated["valor_a_pagar"]) if updated.get("valor_a_pagar") else 0
        confirm = _EDIT_EXPENSE_TEMPLATE.format(**updated)
    else:
        confirm = f"✏️ Gasto #{expense_id} actualizado."

    await update.message.reply_text(confirm)

    sender = user["display_name"]
    shared_before = existing.get("compartida", "No") == "Si"
    shared_after = (merged.get("compartida") or existing.get("compartida", "No")) == "Si"
    if shared_before or shared_after:
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            diff = _build_diff(
                {k: existing.get(k) for k in _EXPENSE_EDITABLE_FIELDS},
                {k: merged.get(k, existing.get(k)) for k in _EXPENSE_EDITABLE_FIELDS},
                set(fields_to_update.keys()) & _EXPENSE_EDITABLE_FIELDS,
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


async def _edit_income(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: dict,
    income_id: int,
    edit_data: dict,
) -> None:
    existing = database.get_income_by_id(income_id)
    if existing is None:
        await update.message.reply_text(f"Ingreso #{income_id} no encontrado.")
        return

    if existing.get("user_id") != user.get("id"):
        await update.message.reply_text("Este ingreso no te pertenece.")
        return

    fields_to_update = {k: v for k, v in edit_data.items() if k in _INCOME_EDITABLE_FIELDS and k != "id"}
    if not fields_to_update:
        await update.message.reply_text(
            f"Ingreso #{income_id} encontrado. ¿Qué quieres cambiar?\n"
            f"Campos editables: valor, concepto, fecha"
        )
        return

    try:
        database.update_income(income_id, fields_to_update)
    except Exception:
        logger.exception("DB update failed for income %s", income_id)
        await update.message.reply_text("Hubo un error al actualizar el ingreso. Intenta de nuevo.")
        return

    updated = database.get_income_by_id(income_id)
    if updated:
        updated["valor"] = int(updated["valor"])
        confirm = _EDIT_INCOME_TEMPLATE.format(**updated)
    else:
        confirm = f"✏️ Ingreso #{income_id} actualizado."

    await update.message.reply_text(confirm)


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    couple_users = database.get_couple_users(user["couple_id"]) if user.get("couple_id") else []
    user_names = tuple(u["display_name"] for u in couple_users) if len(couple_users) == 2 else (sender, "Pareja")

    edit_data = llm.parse_edit(text, sender, date_str, user_names)
    if edit_data is None or "id" not in edit_data:
        await msg.reply_text(_HELP_MSG)
        return

    target_id = edit_data["id"]

    expense = database.get_expense_by_id(target_id)
    if expense is not None:
        await _edit_expense(update, context, user, target_id, edit_data)
        return

    income = database.get_income_by_id(target_id)
    if income is not None:
        await _edit_income(update, context, user, target_id, edit_data)
        return

    await msg.reply_text(f"#{target_id} no encontrado como gasto ni como ingreso.")
