import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4.1")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "finbot")
POSTGRES_USER = os.getenv("POSTGRES_USER", "finbot")
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]

ALLOWED_USER_IDS = {247795192, 1560352087}

USER_MAP = {
    "aron": "Aru",
    "monica": "Mon",
    "mónica": "Mon",
}

# Reverse map: Telegram chat_id → user name (for /token command and API auth)
CHAT_ID_TO_USER: dict[int, str] = {
    247795192: "Aru",
    1560352087: "Mon",
}

# Reverse: user name → chat_id
_NAME_TO_CHAT_ID: dict[str, int] = {v: k for k, v in CHAT_ID_TO_USER.items()}


def get_partner_chat_id(sender_name: str) -> int | None:
    """Return the chat_id of the other user (not sender_name)."""
    for name, chat_id in _NAME_TO_CHAT_ID.items():
        if name != sender_name:
            return chat_id
    return None

# JWT settings for dashboard API
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
API_CORS_ORIGINS = os.getenv("API_CORS_ORIGINS", "http://localhost:3000")

# Aru owes 63% of shared expenses paid by Mon; Mon owes 37% paid by Aru
SPLIT = {"Aru": 0.63, "Mon": 0.37}

MONTH_NAMES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

MONTH_ABBR_ES = {k: v[:3].upper() for k, v in MONTH_NAMES_ES.items()}

CATEGORIES = {
    "ALIMENTACIÓN": [
        "Supermercados", "Mercado Plaza", "Restaurantes",
    ],
    "TRANSPORTE": [
        "Gasolina Carro", "Transp. Público",
    ],
    "VIVIENDA": [
        "Arriendo + Admin", "Servicios Públicos", "Internet",
        "Servicios Técnicos Hogar", "Lencería Hogar", "Activos Fijos Hogar",
    ],
    "SALUD": [
        "AtenciónMéd. Complementaria", "Exámenes Médicos", "Medicina y Suplementos",
    ],
    "EDUCACIÓN": [
        "Formación Académica", "Libros + E-Learning",
    ],
    "ENTRETENIMIENTO": [
        "Actividades Outside", "Plataformas Streaming",
    ],
    "INTERESES": [
        "Pago Intereses",
    ],
    "AHORRO/INVERSIÓN": [
        "Ahorro Pareja",
    ],
    "IMPREVISTOS": [
        "Obsequios", "Otros",
    ],
}
