import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS, MONTH_NAMES_ES
import llm
import finance
import database
import sheets

logger = logging.getLogger(__name__)

_NO_DATA_MSG = "No hay gastos registrados para ese mes."
_SHEETS_ERROR_MSG = "Hubo un error al exportar a Google Sheets. Revisa la configuración del bot."


def _fmt(amount: float) -> str:
    return f"${amount:,.0f}"


def _build_summary(bal: dict) -> str:
    cats = bal["por_categoria"]
    lines = [
        f"📊 Resumen de Gastos — {bal['mes']} 📊",
        "",
        f"Gastos totales del mes: {_fmt(bal['gastos_totales'])}",
        "",
        "💸 Quién gastó:",
        f"  Aron gastó: {_fmt(bal['aron_gasto'])}",
        f"  Mon gastó:  {_fmt(bal['mon_gasto'])}",
        "",
        "⚖️ Saldo pendiente:",
        f"  Aron debe: {_fmt(bal['aron_debe'])}",
        f"  Mon debe:  {_fmt(bal['mon_debe'])}",
        "",
        f"¡{bal['balance_key']}: {_fmt(bal['deuda_total'])}! 😬",
        "",
        "📂 Gastos por categoría:",
    ]
    for cat, val in cats.items():
        if val > 0:
            lines.append(f"  {cat}: {_fmt(val)}")
    return "\n".join(lines)


async def handle_balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    year: int | None = None,
    month: int | None = None,
) -> None:
    msg = update.message
    if msg.chat.id not in ALLOWED_USER_IDS:
        return

    if year is None or month is None:
        text = msg.text or ""
        date_str = msg.date.strftime("%Y-%m-%d")
        year, month = llm.extract_month(text, date_str)

    expenses = database.get_expenses_by_month(year, month)

    if not expenses:
        await msg.reply_text(_NO_DATA_MSG)
        return

    bal = finance.compute_balance(expenses)
    summary = _build_summary(bal)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Ver en Google Sheets", callback_data=f"sheet:{year}:{month}")
    ]])
    await msg.reply_text(summary, reply_markup=keyboard)


async def handle_sheet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.message.chat.id not in ALLOWED_USER_IDS:
        return

    _, year_str, month_str = query.data.split(":")
    year, month = int(year_str), int(month_str)

    expenses = database.get_expenses_by_month(year, month)
    if not expenses:
        await query.message.reply_text(_NO_DATA_MSG)
        return

    try:
        url = sheets.export_month_to_sheet(year, month, expenses)
    except Exception:
        logger.exception("Google Sheets export failed")
        await query.message.reply_text(_SHEETS_ERROR_MSG)
        return

    month_name = MONTH_NAMES_ES.get(month, "")
    await query.message.reply_text(
        f"📊 Gastos de {month_name} {year} exportados:\n{url}"
    )
