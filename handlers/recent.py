import logging
from telegram import Update
from telegram.ext import ContextTypes
import database

logger = logging.getLogger(__name__)

_MAX_LIMIT = 20
_DEFAULT_LIMIT = 5

_EMOJI_MAP = {
    "ALIMENTACIÓN": "🍕",
    "TRANSPORTE": "⛽",
    "VIVIENDA": "🏠",
    "SALUD": "💊",
    "EDUCACIÓN": "📚",
    "ENTRETENIMIENTO": "🎬",
    "INTERESES": "💳",
    "AHORRO/INVERSIÓN": "💰",
    "IMPREVISTOS": "🎁",
}


def _format_expense(e: dict) -> str:
    emoji = _EMOJI_MAP.get(e.get("categoria") or "", "📝")
    concepto = e.get("concepto", "")
    valor = int(e["valor"])
    payer = e["quien_pago"]
    fecha = str(e["fecha"])
    compartida = e.get("compartida", "No")

    parts = [
        f"#{e['id']} {emoji} {concepto}",
        f" — ${valor:,}",
        f" ({payer}, {fecha})",
    ]
    if compartida == "Si":
        parts.append(", compartida")
    return "".join(parts)


async def handle_recent(update: Update, context: ContextTypes.DEFAULT_TYPE, limit: int | None = None) -> None:
    msg = update.message
    user = database.get_user_by_chat_id(msg.chat.id)
    if not user:
        return

    if limit is None:
        limit = _DEFAULT_LIMIT
    limit = max(1, min(limit, _MAX_LIMIT))

    expenses = database.get_recent_expenses(limit)
    if not expenses:
        await msg.reply_text("No hay gastos registrados.")
        return

    lines = [f"📋 Últimos {len(expenses)} gastos:\n"]
    for e in expenses:
        lines.append(_format_expense(e))

    lines.append(f"\nUsa el ID para editar o eliminar:")
    lines.append(f"\"editar gasto {expenses[0]['id']}\" o \"eliminar gasto {expenses[0]['id']}\"")

    await msg.reply_text("\n".join(lines))
