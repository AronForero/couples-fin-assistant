import logging
import os
import gspread
from google.oauth2.service_account import Credentials
from config import MONTH_ABBR_ES

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_SHEET_COLUMNS = [
    "id", "fecha", "quien_pago", "subcategoria", "categoria",
    "concepto", "valor", "compartida", "valor_a_pagar", "observacion",
]


def _get_client() -> gspread.Client:
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not creds_path or not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Service account JSON not found at '{creds_path}'. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON in your .env file."
        )
    creds = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
    return gspread.authorize(creds)


def export_month_to_sheet(year: int, month: int, expenses: list[dict]) -> str:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID is not set in the environment.")

    client = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    tab_name = f"{MONTH_ABBR_ES[month]} {year}"

    try:
        ws = spreadsheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(_SHEET_COLUMNS))

    rows = [_SHEET_COLUMNS]
    for e in expenses:
        rows.append([str(e.get(col, "") or "") for col in _SHEET_COLUMNS])

    ws.update(rows, value_input_option="USER_ENTERED")
    logger.info("Exported %d rows to sheet tab '%s'", len(expenses), tab_name)

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"
