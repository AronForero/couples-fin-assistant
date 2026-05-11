# Technical Documentation — A&M Finances Bot

## Architecture Overview

The system runs as **three independent Docker containers** that share the same PostgreSQL database. The bot and the API do not communicate with each other — they are separate processes with separate entry points, connected only through `database.py`, `finance.py`, and `config.py`.

```
┌───────────────────────────────────────────────────────────────┐
│                      Docker Compose                           │
│                                                               │
│  ┌──────────────┐      ┌─────────────────┐                   │
│  │   bot        │─────▶│                 │                   │
│  │ (bot.py)     │      │                 │                   │
│  └──────────────┘      │   PostgreSQL    │                   │
│                        │   (db)          │                   │
│  ┌──────────────┐      │                 │                   │
│  │   api        │─────▶│                 │                   │
│  │ (api.py)     │      └─────────────────┘                   │
│  └──────┬───────┘                                             │
│         │ :8000                                               │
└─────────┼─────────────────────────────────────────────────────┘
          │
    HTTP + JWT
          │
   ┌──────┴───────┐          ┌──────────────┐
   │  Dashboard   │          │  Telegram    │
   │  (future)    │          │  API         │
   └──────────────┘          └──────┬───────┘
                                    │  polling (HTTPS)
                                    ▼
                              Aru / Mon
```

**Bot path:** Telegram message → `bot.py:dispatch()` → `llm.classify_intent()` → handler → `database.py` → PostgreSQL

**API path:** HTTP request → `api.py` → `api_auth.get_current_user()` (JWT) → `database.py` / `finance.py` → PostgreSQL

External services called at runtime:
- **Telegram API** — receive messages, send replies (long-polling, no inbound port needed)
- **LLM provider** — intent classification, expense parsing, chat replies (configurable via `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`)

---

## Project Structure

```
finbot/
├── bot.py                  # Telegram entry point — handler registration + run_polling()
├── api.py                  # FastAPI entry point — REST API with JWT auth
├── api_auth.py             # JWT create/verify, get_current_user() dependency
├── api_models.py           # Pydantic request/response schemas
├── config.py               # Env vars, constants (IDs, categories, JWT secret)
├── database.py             # PostgreSQL connection, table init, CRUD, get_split()
├── finance.py              # compute_split(), compute_balance() — pure, no I/O
├── llm.py                  # classify_intent(), parse_expense(), extract_month(), chat_reply(), parse_edit(), parse_delete()
├── handlers/
│   ├── expense.py          # handle_expense()
│   ├── balance.py          # handle_balance()
│   ├── chat.py             # handle_chat() — greeting regex + LLM fallback
│   ├── token.py            # handle_token() — /token command for JWT delivery
│   ├── recent.py           # handle_recent() — recent expenses with IDs
│   ├── edit.py             # handle_edit() — edit expense by ID
│   ├── delete.py           # handle_delete() — delete expense by ID with confirmation
│   └── settings.py         # apply_split(), handle_split_command()
├── credentials/            # gitignored — place service_account.json here (future use)
├── docs/                   # This file + features.md
├── version/                # MVP and version specs
├── docker-compose.yml      # db + bot + api services
├── Dockerfile
├── requirements.txt
├── .env.example
├── CLAUDE.md               # Context file for AI assistants
└── AGENTS.md               # Quick reference for AI assistants
```

---

## Message Routing

`bot.py → dispatch()` handles every non-command text message:

```
Text message received
        │
        ▼
  Auth check ──── not in ALLOWED_USER_IDS ──▶ silently return
        │
        ▼
  llm.classify_intent(text, sender, date_str)
        │
        ├── {"intent": "balance",      "params": {"year": 2026, "month": 4}}
        │       └──▶ handle_balance(year, month)
        │
        ├── {"intent": "split_change", "params": {"split_aru": 65.0, "split_mon": 35.0}}
        │       └──▶ apply_split(pct_aru, pct_mon)
        │
        ├── {"intent": "chat",         "params": {}}
        │       └──▶ handle_chat()
        │               ├── greeting regex match → predefined reply
        │               └── otherwise → llm.chat_reply() (LLM fallback)
        │
        ├── {"intent": "recent",       "params": {"limit": 5}}
        │       └──▶ handle_recent(limit)
        │
        ├── {"intent": "edit",         "params": {"id": 42}}
        │       └──▶ handle_edit()
        │
        ├── {"intent": "delete",       "params": {"id": 42}}
        │       └──▶ handle_delete()
        │
        └── {"intent": "expense",      "params": {}}
                └──▶ handle_expense()
```

`classify_intent` fails safely: any exception or unexpected output defaults to `"expense"`.

Commands bypass `dispatch()` and are handled directly:
- `/start` → welcome message
- `/split 65 35` → `handle_split_command()` → `apply_split()`
- `/token` → `handle_token()` → generates JWT for the requesting user
- `/last` or `/last 10` → `last_command()` → `handle_recent(limit)`

---

## LLM Layer (`llm.py`)

Seven functions. Five make JSON completion calls (`temperature=0`, `response_format=json_object`); two make freeform text calls (`temperature=0.7`, `max_tokens=150`).

### `classify_intent(text, sender, date_str) → dict`

Called for **every** incoming message. Returns one of seven intents:
```json
{"intent": "balance",      "params": {"year": 2026, "month": 4}}
{"intent": "split_change", "params": {"split_aru": 65.0, "split_mon": 35.0}}
{"intent": "expense",      "params": {}}
{"intent": "chat",         "params": {}}
{"intent": "recent",       "params": {"limit": 5}}
{"intent": "edit",         "params": {"id": 42}}
{"intent": "delete",       "params": {"id": 42}}
```

Key prompt rules:
- `"expense"` requires a numeric amount — a message like `"cine"` without a number is `"chat"`
- `"edit"` and `"delete"` require an expense ID number — without an ID, the message is `"chat"`
- `"recent"` triggers on keywords like "últimos gastos", "historial", "mis gastos"
- When in doubt between `"split_change"` and `"chat"`, choose `"chat"`
- When in doubt between `"expense"` and `"chat"`, choose `"chat"`
- For `"split_change"`, only return it if both percentages can be confidently extracted and sum to ~100
- For `"balance"`, always return year+month (defaults to current date if not mentioned)

### `parse_expense(text, sender_name, date_str) → dict | None`

Called only when `intent == "expense"`. Returns a structured expense dict or `None` if no valid expense can be extracted.

Returned fields:
```
fecha        YYYY-MM-DD
quien_pago   "Aru" | "Mon"
subcategoria inferred from concept
categoria    inferred from concept
concepto     descriptive text without the number
valor        integer (COP)
compartida   "Si" | "No"
```

Prompt rules:
- Payer defaults to sender; overridden if message mentions "Aru" or "Mon"
- Date defaults to message timestamp; overridden if message mentions a date
- **Shared defaults to "No"** — only `"Si"` if message contains "compartida", "juntos", "entre ambos", "los dos", "dividido" or similar
- Special case: if message ends with "Total: $###", that number is the value and everything before is the concept

### `extract_month(text, current_date) → tuple[int, int]`

Fallback only — called by `handle_balance()` if `classify_intent` didn't return year+month. Returns `(year, month)`.

### `chat_reply(message, sender) → str`

Called when `intent == "chat"` and the message is not a simple greeting. Uses a Spanish system prompt (FinBot personality, 2-3 sentences max, redirects to finance features). Returns freeform text.

### `parse_edit(text, sender_name, date_str) → dict | None`

Called when `intent == "edit"`. Extracts the expense ID and any fields to update from free text.

Returns: `{"id": 42, "compartida": "Si"}` — only includes fields the user mentioned. Returns `None` if no ID found.

### `parse_delete(text, sender_name, date_str) → dict | None`

Called when `intent == "delete"`. Extracts the expense ID from messages like "eliminar gasto 42".

Returns: `{"id": 42}`. Returns `None` if no ID found.

---

## Chat Handler (`handlers/chat.py`)

Hybrid approach for conversational messages:

1. **Greeting path** (regex): Messages matching common Spanish greetings (`hola`, `buenas`, `buenos días`, `qué tal`, etc.) get a random predefined reply from a list of 6 friendly responses.

2. **LLM fallback**: Everything else (questions, jokes, off-topic) calls `llm.chat_reply()`. On LLM error, falls back to a generic help message.

---

## Database Schema

### Table: `expenses`

```sql
CREATE TABLE IF NOT EXISTS expenses (
    id            SERIAL PRIMARY KEY,
    fecha         DATE         NOT NULL,   -- YYYY-MM-DD
    quien_pago    VARCHAR(3)   NOT NULL,   -- 'Aru' | 'Mon'
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,   -- COP, integer
    compartida    VARCHAR(2)   NOT NULL,   -- 'Si' | 'No'
    valor_a_pagar NUMERIC(12,2),          -- amount owed (shared: other's share; personal: full amount)
    observacion   TEXT,                    -- 'Aru Debe' | 'Mon Debe' (only meaningful for shared)
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
```

Month is **not stored** — derived at query time with `EXTRACT(MONTH FROM fecha)`.

### Table: `settings`

```sql
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT        NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seeded on first init:
INSERT INTO settings (key, value) VALUES ('split_aru', '0.63') ON CONFLICT DO NOTHING;
INSERT INTO settings (key, value) VALUES ('split_mon', '0.37') ON CONFLICT DO NOTHING;
```

### Key database functions (`database.py`)

| Function | Description |
|---|---|
| `init_db()` | Creates both tables and seeds split defaults — idempotent |
| `insert_expense(expense: dict) → int` | Inserts one row, returns `id` |
| `get_expenses_by_month(year, month) → list[dict]` | All expenses for a month, ordered by fecha |
| `get_expense_by_id(expense_id) → dict \| None` | Single expense by ID |
| `get_recent_expenses(limit) → list[dict]` | Last N expenses, ordered by id DESC |
| `update_expense(expense_id, fields)` | Update specific fields of an expense by ID |
| `delete_expense(expense_id) → bool` | Delete an expense by ID |
| `get_setting(key, default) → str` | Key/value read with fallback |
| `set_setting(key, value)` | Upsert into settings |
| `get_split() → tuple[float, float]` | Returns `(split_aru, split_mon)` as floats |

---

## Finance Logic (`finance.py`)

### `compute_split(expense, split_aru, split_mon) → dict`

Adds `valor_a_pagar` and `observacion` to an expense dict.

Split direction:
- If **Aru** paid a shared expense → Mon owes `valor × split_mon`; `observacion = "Mon Debe"`
- If **Mon** paid a shared expense → Aru owes `valor × split_aru`; `observacion = "Aru Debe"`
- If **not shared** → full amount stays with payer; `observacion = "{payer} Debe"` (informational only, not used in balance debt calculation)

### `compute_balance(expenses, viewer) → dict`

Aggregates expenses into two sections: **shared** (debt calculation) and **personal** (viewer-only, no debt).

```python
{
    "mes": "Mayo",
    "personal": {
        "viewer": "Aru",
        "viewer_gasto": 50000,        # only Aru's personal expenses
        "gastos_totales": 50000,
        "por_categoria": {"SALUD": 30000, "EDUCACIÓN": 20000, ...}
    },
    "compartido": {
        "aron_gasto": 100000,          # what Aru paid for shared expenses
        "mon_gasto": 60000,            # what Mon paid for shared expenses
        "gastos_totales": 160000,
        "aron_debe": 22200.0,          # sum of valor_a_pagar where observacion == "Aru Debe"
        "mon_debe": 59200.0,           # sum of valor_a_pagar where observacion == "Mon Debe"
        "balance_key": "Mon debe a Aron",
        "deuda_total": 37000.0,        # abs(aron_debe - mon_debe)
        "por_categoria": {"ALIMENTACIÓN": 90000, "ENTRETENIMIENTO": 70000, ...}
    }
}
```

**Privacy model:** The `viewer` parameter filters personal expenses — each user only sees their own. Shared expenses are visible to both users. Debt is only computed on shared expenses.

---

## REST API (`api.py`)

FastAPI application running as a separate container on port 8000. CORS enabled, configurable via `API_CORS_ORIGINS` env var.

### Authentication

All endpoints except `/api/health` require a JWT token in the `Authorization: Bearer <token>` header.

**JWT flow:**
1. User sends `/token` to the Telegram bot
2. Bot generates a JWT with `{"sub": "Aru", "iat": ..., "exp": +30 days}` and replies with it
3. User pastes the token into the dashboard (stored in localStorage)
4. Dashboard sends `Authorization: Bearer <token>` with every request
5. API extracts user from the `sub` claim — used to filter personal expenses

Token details: HS256 algorithm, 30-day expiry, secret from `JWT_SECRET` env var.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | Returns `{"status": "ok"}` |
| `GET` | `/api/expenses?year=&month=` | JWT | List all expenses for a month |
| `POST` | `/api/expenses` | JWT | Create a new expense |
| `GET` | `/api/balance?year=&month=` | JWT | Balance for the authenticated user (shared + personal) |
| `GET` | `/api/settings/split` | JWT | Get current split percentages |
| `PUT` | `/api/settings/split` | JWT | Update split (body: `{"split_aru": 65, "split_mon": 35}`, must sum to 100) |
| `PUT` | `/api/expenses/{id}` | JWT | Update expense fields (partial body) |
| `DELETE` | `/api/expenses/{id}` | JWT | Delete an expense |

### Pydantic models (`api_models.py`)

- `ExpenseCreate` — request body for `POST /api/expenses`
- `ExpenseUpdate` — partial body for `PUT /api/expenses/{id}` (all fields optional)
- `ExpenseResponse` — response for expense endpoints
- `BalanceResponse` — nested with `PersonalBalance` and `SharedBalance`
- `SplitResponse` / `SplitUpdate` — for split settings
- `HealthResponse` — `{"status": "ok"}`

---

## Expense Pipeline

```
handle_expense()
  → llm.parse_expense()          # extracts: fecha, quien_pago, concepto, valor, compartida, categoria, subcategoria
  → database.get_split()         # reads current Aru/Mon percentages from settings table
  → finance.compute_split()      # adds: valor_a_pagar, observacion
  → database.insert_expense()    # saves to expenses table
  → send confirmation to both ALLOWED_USER_IDS
```

Default sharing: expenses are **personal** (`compartida = "No"`) unless the message contains "compartida", "juntos", "entre ambos", "los dos", "dividido" or similar.

---

## Balance Pipeline

```
handle_balance(year, month)
  → resolve sender from msg.chat (via USER_MAP)
  → database.get_expenses_by_month()
  → finance.compute_balance(expenses, viewer=sender)
  → _build_summary(bal)
      ├── 🏠 Compartidos: who paid what, debt, categories
      └── 👤 Personal: viewer's spending + categories (no debt)
  → reply with summary
```

**Privacy:** Each user only sees their own personal expenses. The shared section is visible to both.

---

## Split Pipeline

```
classify_intent → intent = "split_change", params = {split_aru, split_mon}
    → apply_split(pct_aru, pct_mon)          # in handlers/settings.py
        → validate sum = 100 (±0.1)
        → database.set_setting("split_aru", ...) + set_setting("split_mon", ...)
        → confirm to sender
        → notify other user
```

The `/split 65 35` command takes the same path through `apply_split()`.

---

## Recent Expenses Pipeline

```
"últimos gastos" or /last
    → classify_intent → intent = "recent", params = {limit}
    → handle_recent(limit)
        → database.get_recent_expenses(limit)
        → format each expense with ID, emoji, concept, value, payer, date
        → reply with list + hint: "Usa el ID para editar o eliminar"
```

Default limit: 5. Max: 20. User can specify: "últimos 10 gastos" or `/last 15`.

---

## Edit Pipeline

```
"editar gasto 42, era compartido"
    → classify_intent → intent = "edit", params = {id: 42}
    → handle_edit()
        → llm.parse_edit(text) → {id: 42, compartida: "Si"}
        → database.get_expense_by_id(42) → existing expense
        → merge: overwrite only mentioned fields
        → if valor/compartida/quien_pago changed:
            → finance.compute_split() → recompute valor_a_pagar, observacion
        → database.update_expense(42, fields)
        → send updated confirmation to both ALLOWED_USER_IDS
```

Editable fields: `valor`, `concepto`, `fecha`, `compartida`, `quien_pago`, `categoria`, `subcategoria`.

---

## Delete Pipeline

```
"eliminar gasto 42"
    → classify_intent → intent = "delete", params = {id: 42}
    → handle_delete()
        → llm.parse_delete(text) → {id: 42}
        → database.get_expense_by_id(42) → existing expense
        → show expense details + inline keyboard: [Sí, eliminar] [No]
        → callback: delete_confirm:42 → database.delete_expense(42) → notify both
        → callback: delete_cancel:42 → "Gasto no eliminado"
```

---

## Token Command

```
/token → handle_token()
  → look up user from CHAT_ID_TO_USER[chat_id]
  → api_auth.create_token(user)    # JWT with sub=user, exp=+30d
  → reply with token + instructions
```

---

## Docker Compose

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
    volumes:
      - postgres_data:/var/lib/postgresql/data    # named volume — persists across restarts
    healthcheck:
      pg_isready — bot and api wait for this before starting

  bot:
    build: .                                       # from Dockerfile (python:3.12-slim)
    depends_on: db (service_healthy)
    env_file: .env
    restart: unless-stopped

  api:
    build: .                                       # same image, different command
    command: uvicorn api:app --host 0.0.0.0 --port 8000
    depends_on: db (service_healthy)
    env_file: .env
    restart: unless-stopped
    ports:
      - "${API_PORT:-8000}:8000"

volumes:
  postgres_data:
```

Both `bot` and `api` use the same Dockerfile. The `api` service overrides `CMD` via docker-compose to run uvicorn instead of `bot.py`.

---

## Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `TELEGRAM_TOKEN` | Yes | — | From @BotFather |
| `LLM_API_KEY` | Yes | — | API key for your LLM provider |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | No | `openai/gpt-4.1` | Swap provider/model without code change |
| `POSTGRES_HOST` | No | `localhost` | Use `db` in Docker Compose |
| `POSTGRES_PORT` | No | `5432` | |
| `POSTGRES_DB` | No | `finbot` | |
| `POSTGRES_USER` | No | `finbot` | |
| `POSTGRES_PASSWORD` | Yes | — | |
| `JWT_SECRET` | Yes | `change-me` | Secret for signing JWT tokens — change in production |
| `API_PORT` | No | `8000` | Port for the FastAPI container |
| `API_CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated list of allowed origins |

---

## Key Constants (`config.py`)

```python
ALLOWED_USER_IDS = {247795192, 1560352087}   # Aron, Monica

USER_MAP = {"aron": "Aru", "monica": "Mon", "mónica": "Mon"}

CHAT_ID_TO_USER = {247795192: "Aru", 1560352087: "Mon"}   # for /token command

# Default split — seeded into settings table on first run; overridable at runtime via /split
# Aru owes 63% of shared expenses paid by Mon
# Mon owes 37% of shared expenses paid by Aru
```

---

## Deployment

### Local

```bash
cp .env.example .env
# edit .env with real values (TELEGRAM_TOKEN, LLM_API_KEY, POSTGRES_PASSWORD, JWT_SECRET)
docker compose up
```

### VPS

```bash
git clone <repo> finbot && cd finbot
cp .env.example .env && nano .env
docker compose up -d
```

Data persists in the `postgres_data` Docker volume across restarts and image rebuilds.

---

## Error Handling

| Situation | Response |
|---|---|
| Message with no concept or value | Spanish help message with usage example |
| Database write failure | Generic error message; exception logged |
| Unauthorised user (bot) | Silent ignore |
| Unauthorised user (API) | HTTP 401 with error detail |
| Unknown intent | Treated as expense attempt; falls back to help message if parsing fails |
| Chat LLM failure | Generic help message as fallback |
| Greeting message | Predefined random reply (no LLM call) |
| Edit with no ID | Help message showing edit syntax |
| Edit with invalid ID | "Gasto #N no encontrado" |
| Delete with no ID | Help message showing delete syntax |
| Delete with invalid ID | "Gasto #N no encontrado" |
| API: expense not found | HTTP 404 |

---

## Adding a New Intent

1. **`llm.py → _CLASSIFIER_SYSTEM`** — add the new intent name, its description, and the params it should return
2. **`handlers/`** — create `handlers/your_feature.py` with an async handler function
3. **`bot.py → dispatch()`** — add `elif intent == "your_intent": await your_handler(...)` and import it
4. If the handler needs a Telegram command shortcut, register it with `app.add_handler(CommandHandler("cmd", fn))`
