import json
import logging
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, CATEGORIES

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

_CATEGORIES_TEXT = "\n".join(
    f"- {cat}: {', '.join(subs)}" for cat, subs in CATEGORIES.items()
)


# ── Dynamic prompt builders ──────────────────────────────────────────────────

def _build_classifier_system(user1: str, user2: str) -> str:
    return f"""You are an intent classifier for a personal finance Telegram bot used by two people: {user1} and {user2}.

Classify the user message into exactly one of seven intents and extract any parameters. Return ONLY a JSON object — no explanation.

Intents:
1. "balance" — user wants to see their expense summary for a month.
   Params: {{"year": <int>, "month": <int>}}
   If no month is mentioned, use the current date provided.

2. "split_change" — user wants to change the shared expense percentage between {user1} and {user2}.
   Params: {{"split_user1": <float>, "split_user2": <float>}}
   Both values are percentages (e.g. 65.0 and 35.0). They must sum to 100.
   If the user mentions only one value and says "yo" (I), use the sender name to infer which person they mean and compute the other value as 100 minus the first.

3. "expense" — registering a purchase or expense. The message must contain both a concept and a numeric value/amount.
   Params: {{}}

4. "chat" — greetings, casual conversation, questions about the bot, jokes, compliments, thanks, or any message that is clearly NOT an expense, balance query, or split change.
   Params: {{}}

5. "recent" — user wants to see their recent/latest expenses. Triggered by "últimos gastos", "gastos recientes", "historial", "mis gastos", "ver gastos", etc.
   Params: {{"limit": <int>}} — number of expenses to show. Default 5 if not specified.

6. "edit" — user wants to modify/correct an existing expense. Must contain an expense ID number (shown as #N in confirmations).
   Params: {{"id": <int>}}

7. "delete" — user wants to remove/delete an existing expense. Must contain an expense ID number.
   Params: {{"id": <int>}}

Rules:
- "expense" requires a numeric amount. A message like "cine" without a number is "chat".
- "edit" and "delete" require an expense ID number. If no ID is present, treat as "chat".
- When in doubt between "split_change" and "chat", choose "chat".
- When in doubt between "expense" and "chat", choose "chat".
- "edit" keywords: "editar", "corregir", "modificar", "cambia el gasto", "el gasto X era/era en realidad".
- "delete" keywords: "eliminar", "borrar", "quitar", "quita el gasto".
- "recent" keywords: "últimos", "recientes", "historial", "ver gastos", "mis gastos".

Return format examples:
{{"intent": "balance", "params": {{"year": 2026, "month": 4}}}}
{{"intent": "split_change", "params": {{"split_user1": 65.0, "split_user2": 35.0}}}}
{{"intent": "expense", "params": {{}}}}
{{"intent": "chat", "params": {{}}}}
{{"intent": "recent", "params": {{"limit": 5}}}}
{{"intent": "edit", "params": {{"id": 42}}}}
{{"intent": "delete", "params": {{"id": 42}}}}"""


def _build_expense_system(user1: str, user2: str, categories_text: str) -> str:
    return f"""Eres un asistente de finanzas personales. Tu ÚNICA tarea es extraer datos de un gasto a partir del mensaje del usuario y devolver un objeto JSON válido, o null si el mensaje no contiene un gasto.

Reglas de extracción:
1. Valor: cualquier número positivo en el mensaje. Si el mensaje TERMINA con "Total: $###", ese número es el Valor y todo lo anterior es el Concepto.
2. Concepto: texto descriptivo del gasto, sin incluir el número.
3. Quien pagó: si el mensaje menciona "{user1}" o "{user2}", usa ese. Si no, usa el remitente.
4. Fecha: si el mensaje menciona una fecha específica (ej. "ayer", "01/7"), úsala. Si no, usa la fecha del mensaje.
5. Compartida: "Si" si el mensaje contiene "compartida", "juntos", "entre ambos", "los dos", "dividido" o frases similares. Si no, "No".
6. Categoría y SubCategoría: infiere del concepto usando esta lista:
{categories_text}

Devuelve EXACTAMENTE este JSON (sin texto adicional):
{{
  "fecha": "YYYY-MM-DD",
  "quien_pago": "{user1}" o "{user2}",
  "subcategoria": "...",
  "categoria": "...",
  "concepto": "...",
  "valor": 12345,
  "compartida": "Si" o "No"
}}

Si el mensaje NO contiene un concepto y un valor numérico, devuelve exactamente: null"""


def _build_chat_system(user1: str, user2: str) -> str:
    return f"""Eres un bot de finanzas personales para una pareja: {user1} y {user2}.
Tu nombre es FinBot. Hablas en español de forma amigable, breve y con buena onda.
Si te preguntan qué puedes hacer, menciona que puedes registrar gastos, mostrar el balance mensual y cambiar el porcentaje de gastos compartidos.
Si el usuario saluda, responde de forma cálida y breve.
Si te hacen preguntas fuera de tema, responde brevemente y redirige amablemente a tus funciones de finanzas.
Nunca inventes datos financieros. Máximo 2-3 oraciones."""


def _build_edit_system(user1: str, user2: str, categories_text: str) -> str:
    return f"""Eres un asistente de finanzas personales. Tu tarea es extraer el ID del gasto a editar y los campos que el usuario quiere cambiar.

Devuelve SOLO un objeto JSON con el ID y los campos a modificar. Solo incluye los campos que el usuario menciona explícitamente.

Campos editables:
- id: número del gasto (obligatorio)
- valor: monto numérico
- concepto: descripción del gasto
- fecha: fecha en formato YYYY-MM-DD
- compartida: "Si" o "No"
- quien_pago: "{user1}" o "{user2}"
- categoria: categoría del gasto
- subcategoria: subcategoría del gasto

Categorías disponibles:
{categories_text}

Ejemplos:
- "editar gasto 42, era compartido" → {{"id": 42, "compartida": "Si"}}
- "gasto 42, el valor era 25000" → {{"id": 42, "valor": 25000}}
- "editar gasto 42, concepto verduras del mercado, valor 25000" → {{"id": 42, "concepto": "verduras del mercado", "valor": 25000}}
- "corregir gasto 38, pagó {user2}" → {{"id": 38, "quien_pago": "{user2}"}}
- "cambia el gasto 42 a no compartida" → {{"id": 42, "compartida": "No"}}

Si el mensaje NO contiene un ID de gasto, devuelve exactamente: null"""


_DELETE_SYSTEM = """Eres un asistente de finanzas personales. Tu tarea es extraer el ID del gasto a eliminar del mensaje del usuario.

Devuelve SOLO un objeto JSON con el ID del gasto.

Ejemplos:
- "eliminar gasto 42" → {"id": 42}
- "borrar gasto 38" → {"id": 38}
- "quita el gasto 42" → {"id": 42}
- "eliminar el gasto número 15" → {"id": 15}

Si el mensaje NO contiene un ID de gasto, devuelve exactamente: null"""


# ── LLM helpers ──────────────────────────────────────────────────────────────

def _chat_json(system: str, user: str) -> dict | None:
    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _chat_text(system: str, user: str, max_tokens: int = 150) -> str:
    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


# ── Public functions ─────────────────────────────────────────────────────────

def classify_intent(text: str, sender: str, date_str: str, user_names: tuple[str, str] = ("Aru", "Mon")) -> dict:
    """
    Returns {"intent": "balance"|"split_change"|"expense"|"chat"|"recent"|"edit"|"delete", "params": {...}}.
    Falls back to expense intent on any error.
    """
    system = _build_classifier_system(user_names[0], user_names[1])
    user_msg = f"Sender: {sender}\nCurrent date: {date_str}\nMessage: {text}"
    try:
        data = _chat_json(system, user_msg)
        intent = data.get("intent", "expense")
        params = data.get("params", {})
        if intent not in {"balance", "split_change", "expense", "chat", "recent", "edit", "delete"}:
            intent = "expense"
        return {"intent": intent, "params": params}
    except Exception:
        logger.exception("classify_intent failed, defaulting to expense")
        return {"intent": "expense", "params": {}}


def parse_expense(text: str, sender_name: str, date_str: str, user_names: tuple[str, str] = ("Aru", "Mon")) -> dict | None:
    system = _build_expense_system(user_names[0], user_names[1], _CATEGORIES_TEXT)
    user_msg = f"Remitente: {sender_name}\nFecha del mensaje: {date_str}\nMensaje: {text}"
    parsed = _chat_json(system, user_msg)
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
    data = _chat_json(_MONTH_SYSTEM, user_msg)
    return int(data["year"]), int(data["month"])


def chat_reply(message: str, sender: str, user_names: tuple[str, str] = ("Aru", "Mon")) -> str:
    """Generate a conversational reply for non-expense messages."""
    system = _build_chat_system(user_names[0], user_names[1])
    user_msg = f"Remitente: {sender}\nMensaje: {message}"
    return _chat_text(system, user_msg)


def parse_edit(text: str, sender_name: str, date_str: str, user_names: tuple[str, str] = ("Aru", "Mon")) -> dict | None:
    """Extract expense ID and fields to update from an edit message."""
    system = _build_edit_system(user_names[0], user_names[1], _CATEGORIES_TEXT)
    user_msg = f"Remitente: {sender_name}\nFecha del mensaje: {date_str}\nMensaje: {text}"
    try:
        parsed = _chat_json(system, user_msg)
        if parsed is None:
            return None
        if set(parsed.keys()) == {"result"}:
            parsed = parsed["result"]
        if not parsed or "id" not in parsed:
            return None
        return parsed
    except Exception:
        logger.exception("parse_edit failed")
        return None


def parse_delete(text: str, sender_name: str, date_str: str) -> dict | None:
    """Extract expense ID from a delete message."""
    user_msg = f"Remitente: {sender_name}\nFecha del mensaje: {date_str}\nMensaje: {text}"
    try:
        parsed = _chat_json(_DELETE_SYSTEM, user_msg)
        if parsed is None:
            return None
        if set(parsed.keys()) == {"result"}:
            parsed = parsed["result"]
        if not parsed or "id" not in parsed:
            return None
        return parsed
    except Exception:
        logger.exception("parse_delete failed")
        return None
