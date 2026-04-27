import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, LLM_MODEL, CATEGORIES

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=OPENAI_API_KEY)

_CATEGORIES_TEXT = "\n".join(
    f"- {cat}: {', '.join(subs)}" for cat, subs in CATEGORIES.items()
)

_CLASSIFIER_SYSTEM = """You are an intent classifier for a personal finance Telegram bot used by two people: Aru and Mon.

Classify the user message into exactly one of three intents and extract any parameters. Return ONLY a JSON object — no explanation.

Intents:
1. "balance" — user wants to see their expense summary for a month.
   Params: {"year": <int>, "month": <int>}
   If no month is mentioned, use the current date provided.

2. "split_change" — user wants to change the shared expense percentage between Aru and Mon.
   Params: {"split_aru": <float>, "split_mon": <float>}
   Both values are percentages (e.g. 65.0 and 35.0). They must sum to 100.
   If the user mentions only one value and says "yo" (I), use the sender name to infer which person they mean and compute the other value as 100 minus the first.

3. "expense" — anything else: registering a purchase, greeting, question, unrecognised input.
   Params: {}

Rules:
- When in doubt between "split_change" and "expense", choose "expense".
- If you detect "split_change" but cannot confidently extract both percentages summing to 100, return "expense" instead.

Return format examples:
{"intent": "balance", "params": {"year": 2026, "month": 4}}
{"intent": "split_change", "params": {"split_aru": 65.0, "split_mon": 35.0}}
{"intent": "expense", "params": {}}"""

_EXPENSE_SYSTEM = f"""Eres un asistente de finanzas personales. Tu ÚNICA tarea es extraer datos de un gasto a partir del mensaje del usuario y devolver un objeto JSON válido, o null si el mensaje no contiene un gasto.

Reglas de extracción:
1. Valor: cualquier número positivo en el mensaje. Si el mensaje TERMINA con "Total: $###", ese número es el Valor y todo lo anterior es el Concepto.
2. Concepto: texto descriptivo del gasto, sin incluir el número.
3. Quien pagó: si el mensaje menciona "Aru" o "Mon", usa ese. Si no, usa el remitente.
4. Fecha: si el mensaje menciona una fecha específica (ej. "ayer", "01/07"), úsala. Si no, usa la fecha del mensaje.
5. Compartida: "No" si el mensaje contiene "no compartida". Si no, "Si".
6. Categoría y SubCategoría: infiere del concepto usando esta lista:
{_CATEGORIES_TEXT}

Devuelve EXACTAMENTE este JSON (sin texto adicional):
{{
  "fecha": "YYYY-MM-DD",
  "quien_pago": "Aru" o "Mon",
  "subcategoria": "...",
  "categoria": "...",
  "concepto": "...",
  "valor": 12345,
  "compartida": "Si" o "No"
}}

Si el mensaje NO contiene un concepto y un valor numérico, devuelve exactamente: null"""


def classify_intent(text: str, sender: str, date_str: str) -> dict:
    """
    Returns {"intent": "balance"|"split_change"|"expense", "params": {...}}.
    Falls back to expense intent on any error.
    """
    user_msg = f"Sender: {sender}\nCurrent date: {date_str}\nMessage: {text}"
    try:
        resp = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        intent = data.get("intent", "expense")
        params = data.get("params", {})
        if intent not in {"balance", "split_change", "expense"}:
            intent = "expense"
        return {"intent": intent, "params": params}
    except Exception:
        logger.exception("classify_intent failed, defaulting to expense")
        return {"intent": "expense", "params": {}}


def parse_expense(text: str, sender_name: str, date_str: str) -> dict | None:
    user_msg = f"Remitente: {sender_name}\nFecha del mensaje: {date_str}\nMensaje: {text}"
    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _EXPENSE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    parsed = json.loads(raw)
    if parsed is None:
        return None
    if set(parsed.keys()) == {"result"}:
        return parsed["result"]
    required = {"fecha", "quien_pago", "concepto", "valor", "compartida"}
    if not required.issubset(parsed.keys()):
        return None
    return parsed


def extract_month(text: str, current_date: str) -> tuple[int, int]:
    """Fallback month extractor — used when year/month were not pre-extracted by classify_intent."""
    _MONTH_SYSTEM = """Extract the month and year from the user message.
Return ONLY a JSON object: {"year": 2026, "month": 4}
If no month is mentioned, use the current date provided.
Never add any explanation."""
    user_msg = f"Current date: {current_date}\nMessage: {text}"
    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _MONTH_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return int(data["year"]), int(data["month"])
