import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-nano")

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
