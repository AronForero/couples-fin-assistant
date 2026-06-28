# Technical Documentation — FinDuo

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
finduo/
├── bot.py                  # Telegram entry point — handler registration + run_polling()
├── api.py                  # FastAPI entry point — REST API with JWT auth
├── api_auth.py             # JWT create/verify, get_current_user() dependency
├── api_models.py           # Pydantic request/response schemas
├── config.py               # Env vars, constants (IDs, categories, JWT secret)
├── database/               # PostgreSQL layer — package with one module per concern
│   ├── __init__.py         #   re-exports the public API (backward-compatible import as `database`)
│   ├── connection.py       #   get_conn() — plain psycopg2.connect, no pool
│   ├── schema.py           #   CREATE TABLE DDL + migration SQL
│   ├── init.py             #   init_db() orchestration + seed split defaults
│   ├── utils.py            #   generate_invite_code()
│   ├── users.py            #   user CRUD, is_user_active, status updates
│   ├── couples.py          #   couple lifecycle (create, join, leave, history)
│   ├── couple_settings.py  #   split percentage CRUD per couple
│   ├── expenses.py         #   expense CRUD (insert, get_by_id, update, delete, recent, by_month, by_date_range)
│   └── incomes.py          #   income CRUD (mirrors expenses)
├── finance.py              # compute_split(), compute_balance(), compute_actual_money() — pure, no I/O
├── llm.py                  # classify_intent(), parse_expense(), parse_income(), extract_month(),
│                           # chat_reply(), parse_edit(), parse_delete()
├── handlers/
│   ├── expense.py          # handle_expense()
│   ├── income.py           # handle_income()
│   ├── balance.py          # handle_balance()
│   ├── chat.py             # handle_chat() — greeting regex + LLM fallback
│   ├── link.py             # handle_link() — /link command for Telegram account linking
│   ├── recent.py           # handle_recent() — recent expenses with IDs
│   ├── edit.py             # handle_edit() — edit expense or income by ID
│   ├── delete.py           # handle_delete() — delete expense or income by ID (logs every step,
│   │                       #                    checks delete_*() return value, no second LLM call
│   │                       #                    when classify_intent already extracted an id)
│   ├── actual_money.py     # handle_actual_money() — "Tu dinero real" view
│   └── settings.py         # apply_split(), handle_split_command()
├── credentials/            # gitignored — place service_account.json here (future use)
├── docs/                   # This file + features.md + version specs
├── docker-compose.yml      # db + bot + api services (dashboard service added from
│                           # the dashboard repo's docker-compose.snippet.yml)
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
  llm.classify_intent(text, sender, date_str, user_names)
        │
        ├── {"intent": "balance",      "params": {"year": 2026, "month": 4}}
        │       └──▶ handle_balance(year=2026, month=4)
        │
        ├── {"intent": "split_change", "params": {"split_user1": 65.0, "split_user2": 35.0}}
        │       └──▶ apply_split(pct_user1, pct_user2)
        │
        ├── {"intent": "chat",         "params": {}}
        │       └──▶ handle_chat()
        │               ├── greeting regex match → predefined reply
        │               └── otherwise → llm.chat_reply() (LLM fallback)
        │
        ├── {"intent": "recent",       "params": {"limit": 5}}
        │       └──▶ handle_recent(limit=5)
        │
        ├── {"intent": "edit",         "params": {"id": 42}}
        │       └──▶ handle_edit()
        │
        ├── {"intent": "delete",       "params": {"id": 42}}
        │       └──▶ handle_delete(target_id=42)
        │
        ├── {"intent": "income",       "params": {}}
        │       └──▶ handle_income()
        │
        ├── {"intent": "actual_money", "params": {"year": 2026, "month": 4}}
        │       └──▶ handle_actual_money(year=2026, month=4)
        │
        └── {"intent": "expense",      "params": {}}
                └──▶ handle_expense()
```

`classify_intent` fails safely: any exception or unexpected output defaults to `"expense"`.

The `"delete"` intent passes the extracted `id` directly to `handle_delete` via the `target_id` parameter — no second LLM call is made. The `"edit"` handler still re-parses the message via `llm.parse_edit()` (it needs the field changes from the user text, not just the id).

Commands bypass `dispatch()` and are handled directly:
- `/start` → welcome message
- `/link <email>` → `handle_link()` — links Telegram chat_id to user account
- `/split 65 35` → `handle_split_command()` → `apply_split()`
- `/last` or `/last 10` → `last_command()` → `handle_recent(limit)`

---

## LLM Layer (`llm.py`)

Eight public functions. Six make JSON completion calls (`temperature=0`, `response_format=json_object`); two make freeform text calls (`temperature=0.7`, `max_tokens=150`).

### `classify_intent(text, sender, date_str, user_names) → dict`

Called for **every** incoming message. Returns one of nine intents plus optional params:
```json
{"intent": "balance",      "params": {"year": 2026, "month": 4}}
{"intent": "split_change", "params": {"split_user1": 65.0, "split_user2": 35.0}}
{"intent": "expense",      "params": {}}
{"intent": "chat",         "params": {}}
{"intent": "recent",       "params": {"limit": 5}}
{"intent": "edit",         "params": {"id": 42}}
{"intent": "delete",       "params": {"id": 42}}
{"intent": "income",       "params": {}}
{"intent": "actual_money", "params": {"year": null, "month": null}}
```

Key prompt rules:
- `"expense"` requires a numeric amount — a message like `"cine"` without a number is `"chat"`
- `"income"` requires a numeric amount AND an income keyword — without either, fall back to `"chat"`
- `"edit"` and `"delete"` require an ID number — without an ID, the message is `"chat"`
- `"actual_money"` is triggered by phrases like "cuánto tengo", "mi dinero", "dinero real", "cuánto me queda"
- `"recent"` triggers on keywords like "últimos gastos", "historial", "mis gastos"
- When in doubt between `"split_change"` and `"chat"`, choose `"chat"`
- When in doubt between `"expense"` and `"chat"`, choose `"chat"`
- When in doubt between `"income"` and `"chat"`, choose `"chat"`
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

Called when `intent == "chat"` and the message is not a simple greeting. Uses a Spanish system prompt (FinDuo personality, 2-3 sentences max, redirects to finance features). Returns freeform text.

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
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,   -- COP, integer
    compartida    VARCHAR(2)   NOT NULL,   -- 'Si' | 'No'
    valor_a_pagar NUMERIC(12,2),          -- amount owed (shared: other's share; personal: full amount)
    quien_pago_id INTEGER      REFERENCES users(id),  -- FK to payer
    debt_user_id  INTEGER      REFERENCES users(id),  -- FK to debtor
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

### Key database functions (`database/`)

`database.py` is now a package (`database/`) with per-concern modules. All functions below are re-exported by `database/__init__.py` so existing callers can still `import database; database.delete_expense(...)`.

| Function | Module | Description |
|---|---|---|
| `init_db()` | `init.py` | Creates all tables and seeds defaults — idempotent |
| `get_conn()` | `connection.py` | Returns a fresh psycopg2 connection (no pool) |
| `create_user(email, password, display_name)` | `users.py` | Insert user, returns user dict |
| `get_user_by_chat_id(chat_id)` | `users.py` | Look up user by Telegram chat_id |
| `get_user_by_email(email)` | `users.py` | Look up user by email |
| `get_couple_users(couple_id)` | `users.py` | Both members of a couple |
| `get_partner(user_id)` | `users.py` | The other user in the couple |
| `is_user_active(user) → bool` | `users.py` | True if `status` is `"active"` or trial not expired |
| `update_user_status(user_id, status)` | `users.py` | Set trial/active/suspended |
| `create_couple(user_id)` | `couples.py` | New couple + invite_code, links user |
| `join_couple(user_id, invite_code)` | `couples.py` | Link user to existing couple |
| `leave_couple(user_id)` | `couples.py` | Set `couple_id = NULL` for user |
| `get_user_couples(user_id)` | `couples.py` | Couple history (active + past) |
| `get_couple_expenses(couple_id, year, month)` | `couples.py` | Read-only historical expenses |
| `get_split_for_couple(couple_id)` | `couple_settings.py` | `{user_id: pct}` dict for the couple |
| `update_split_for_couple(couple_id, splits)` | `couple_settings.py` | Upsert split percentages |
| `generate_invite_code()` | `utils.py` | 8-char random alphanumeric |
| `insert_expense(expense) → int` | `expenses.py` | Insert row, return id |
| `get_expenses_by_month(year, month, couple_id)` | `expenses.py` | Expenses for a month scoped to a couple |
| `get_expenses_by_month_and_users(year, month, user_ids, couple_id)` | `expenses.py` | Same, restricted to a list of user ids |
| `get_expenses_by_date_range(couple_id, start, end)` | `expenses.py` | Expenses for a couple in an inclusive date range |
| `get_expense_by_id(id) → dict \| None` | `expenses.py` | Single expense by ID (returns `couple_id`, `quien_pago_id`, `debt_user_id`) |
| `get_recent_expenses(limit, couple_id)` | `expenses.py` | Last N expenses for the couple, ordered by id DESC |
| `update_expense(id, fields) → bool` | `expenses.py` | Update specific fields by ID |
| `delete_expense(id) → bool` | `expenses.py` | Hard DELETE by ID — returns `rowcount > 0` |
| `insert_income(income) → int` | `incomes.py` | Insert row, return id |
| `get_incomes_by_month(year, month, user_id)` | `incomes.py` | Incomes for a month scoped to a user |
| `get_incomes_by_date_range(user_id, start, end)` | `incomes.py` | Incomes in an inclusive date range |
| `get_income_by_id(id) → dict \| None` | `incomes.py` | Single income by ID |
| `get_recent_incomes(limit, user_id)` | `incomes.py` | Last N incomes for the user |
| `update_income(id, fields) → bool` | `incomes.py` | Update specific fields by ID |
| `delete_income(id) → bool` | `incomes.py` | Hard DELETE by ID — returns `rowcount > 0` |

---

## Finance Logic (`finance.py`)

### `compute_split(expense, split_aru, split_mon) → dict`

Adds `valor_a_pagar` and `debt_user_id` to an expense dict.

Split direction:
- If **Aru** paid a shared expense → Mon owes `valor × split_mon`; `debt_user_id = partner_id`
- If **Mon** paid a shared expense → Aru owes `valor × split_aru`; `debt_user_id = partner_id`
- If **not shared** → full amount stays with payer; `debt_user_id = payer_id` (informational only)

### `compute_balance(expenses, viewer_id, users) → dict`

Aggregates expenses into two sections: **shared** (debt calculation) and **personal** (viewer-only, no debt).

```python
{
    "mes": "Mayo",
    "personal": {
        "viewer_id": 1,
        "viewer_name": "Aru",
        "viewer_gasto": 50000,        # only Aru's personal expenses
        "gastos_totales": 50000,
        "por_categoria": {"SALUD": 30000, "EDUCACIÓN": 20000, ...}
    },
    "compartido": {
        "gastos": [100000, 60000],    # per-user amounts, ordered by sorted(users.keys())
        "deudas": [22200.0, 59200.0],  # per-user debts, same ordering
        "gastos_totales": 160000,
        "balance_key": "Mon debe a Aru",  # or "Pagaron lo mismo" if deuda_total == 0
        "deuda_total": 37000.0,         # abs difference between the two debts
        "por_categoria": {"ALIMENTACIÓN": 90000, "ENTRETENIMIENTO": 70000, ...}
    }
}
```

**Privacy model:** The `viewer_id` parameter filters personal expenses — each user only sees their own. Shared expenses are visible to both users. Debt is only computed on shared expenses.

`gastos` and `deudas` are **ordered arrays**, indexed by `sorted(users.keys())`. This matches the ordering used by the dashboard frontend's `BalanceCard` component (which also expects an array indexed by `memberNames`). Callers that need a per-user map can `zip(sorted_uids, gastos)`.

---

## REST API (`api.py`)

FastAPI application running as a separate container on port 8000. CORS enabled, configurable via `API_CORS_ORIGINS` env var.

### Authentication

All endpoints except `/api/health`, `/api/auth/register`, and `/api/auth/login` require a JWT token in the `Authorization: Bearer <token>` header.

**JWT flow:**
1. User registers or logs in via the dashboard (`POST /api/auth/register` or `POST /api/auth/login`)
2. API returns a JWT with `{"sub": user_id, "iat": ..., "exp": +30 days}`
3. Dashboard stores the token (e.g. localStorage) and sends `Authorization: Bearer <token>` with every request
4. API extracts user ID from the `sub` claim — used to scope data to the user's couple

Token details: HS256 algorithm, 30-day expiry, secret from `JWT_SECRET` env var.

**Telegram linking:** Users who register via the API can link their Telegram account with `/link <email>` in the bot. This sets their `chat_id` in the DB, enabling bot access.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | Returns `{"status": "ok"}` |
| `POST` | `/api/auth/register` | No | Create user + couple, returns JWT |
| `POST` | `/api/auth/login` | No | Email/password login, returns JWT |
| `POST` | `/api/auth/join` | JWT | Join couple via invite code |
| `GET` | `/api/auth/me` | JWT | Current user info |
| `GET` | `/api/auth/couple/members` | JWT | Both users in the couple |
| `GET` | `/api/expenses?year=&month=` | JWT | List all expenses for a month |
| `POST` | `/api/expenses` | JWT | Create a new expense |
| `GET` | `/api/balance?year=&month=` | JWT | Balance for the authenticated user (shared + personal) |
| `GET` | `/api/settings/split` | JWT | Get current split percentages |
| `PUT` | `/api/settings/split` | JWT | Update split (body: `{"splits": {1: 0.65, 2: 0.35}}`) |
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
  → finance.compute_split()      # adds: valor_a_pagar, debt_user_id
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
            → finance.compute_split() → recompute valor_a_pagar, debt_user_id
        → database.update_expense(42, fields)
        → send updated confirmation to both ALLOWED_USER_IDS
```

Editable fields: `valor`, `concepto`, `fecha`, `compartida`, `quien_pago`, `categoria`, `subcategoria`.

---

## Delete Pipeline

```
"eliminar gasto 42"
    → classify_intent → intent = "delete", params = {id: 42}
    → handle_delete(target_id=42)            # id passed directly, no second LLM call
        → database.get_expense_by_id(42)
        → if found and couple_id matches user's couple:
            → deleted = database.delete_expense(42)
            → if deleted (rowcount > 0):
                → reply "🗑 Gasto #42 eliminado: <concepto> — $<valor>"
                → if compartida == "Si": notify partner via Telegram
            → else (delete_expense returned False, 0 rows affected):
                → reply "No se pudo eliminar el gasto #42 (¿ya fue borrado?)..."
        → if expense not found:
            → database.get_income_by_id(42)
            → if found and user_id matches: same flow with delete_income()
            → else: reply "#42 no encontrado como gasto ni como ingreso"
```

The handler **logs every decision** at INFO level (sender, chat_id, target_id extraction source, lookup results, deletion result) so failures are diagnosable in `docker logs` without needing to reproduce them. The `delete_expense()` / `delete_income()` return value (a `bool` indicating whether a row was actually deleted) is **checked** — the success message is only sent when a row was removed.

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
| `POSTGRES_DB` | No | `finduo` | |
| `POSTGRES_USER` | No | `finduo` | |
| `POSTGRES_PASSWORD` | Yes | — | |
| `JWT_SECRET` | Yes | `change-me` | Secret for signing JWT tokens — change in production |
| `API_PORT` | No | `8000` | Port for the FastAPI container |
| `API_CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated list of allowed origins |

---

## Key Constants (`config.py`)

```python
# JWT settings for dashboard API
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
API_CORS_ORIGINS = os.getenv("API_CORS_ORIGINS", "http://localhost:3000")
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
git clone <repo> finduo && cd finduo
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
| Delete where row already gone | "No se pudo eliminar el gasto #N (¿ya fue borrado?)..." (WARNING logged) |
| Balance over an empty month | "No hay gastos registrados para ese mes." |
| API: expense not found | HTTP 404 |

---

## Adding a New Intent

1. **`llm.py → _CLASSIFIER_SYSTEM`** — add the new intent name, its description, and the params it should return
2. **`handlers/`** — create `handlers/your_feature.py` with an async handler function
3. **`bot.py → dispatch()`** — add `elif intent == "your_intent": await your_handler(...)` and import it
4. If the handler needs a Telegram command shortcut, register it with `app.add_handler(CommandHandler("cmd", fn))`
