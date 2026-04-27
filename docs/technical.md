# Technical Documentation — A&M Finances Bot

## Architecture Overview

The bot is a single-process async Python application. There is no webhook or public-facing server — it uses Telegram's **long-polling** API, so no SSL certificate or open port is required.

```
┌─────────────────────────────────────────────┐
│               Docker Compose                │
│                                             │
│  ┌──────────────┐      ┌─────────────────┐  │
│  │   bot        │─────▶│   db            │  │
│  │ (Python 3.12)│      │ (PostgreSQL 16) │  │
│  └──────┬───────┘      └─────────────────┘  │
│         │ ./credentials (read-only volume)  │
└─────────┼───────────────────────────────────┘
          │
          │  polling (HTTPS, no inbound port needed)
          ▼
      Telegram API
          ▲
          │  messages
    Aru / Mon
```

External services called at runtime:
- **Telegram API** — receive messages, send replies, handle inline button callbacks
- **OpenAI API** — intent classification and expense parsing (every message)
- **Google Sheets API** — only when a user taps "📊 Ver en Google Sheets"

---

## Project Structure

```
finbot/
├── bot.py                  # Entry point, handler registration, polling
├── config.py               # Env vars, constants (IDs, categories, month maps)
├── database.py             # PostgreSQL connection, table init, CRUD, get_split()
├── finance.py              # compute_split(), compute_balance() — pure, no I/O
├── llm.py                  # classify_intent(), parse_expense(), extract_month()
├── sheets.py               # export_month_to_sheet() via gspread
├── handlers/
│   ├── expense.py          # handle_expense()
│   ├── balance.py          # handle_balance(), handle_sheet_callback()
│   └── settings.py         # apply_split(), handle_split_command()
├── credentials/            # gitignored; place service_account.json here
├── docs/                   # This file + features.md
├── version/                # MVP and version specs
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
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
        └── {"intent": "expense",      "params": {}}
                └──▶ handle_expense()
```

`classify_intent` fails safely: any exception or unexpected output defaults to `"expense"`.

Commands bypass `dispatch()` and are handled directly:
- `/start` → welcome message
- `/split 65 35` → `handle_split_command()` → `apply_split()`

---

## LLM Layer (`llm.py`)

Three functions, each making one OpenAI chat completion call with `temperature=0` and `response_format={"type": "json_object"}`.

### `classify_intent(text, sender, date_str) → dict`

Called for **every** incoming message. Returns one of:
```json
{"intent": "balance",      "params": {"year": 2026, "month": 4}}
{"intent": "split_change", "params": {"split_aru": 65.0, "split_mon": 35.0}}
{"intent": "expense",      "params": {}}
```

Key prompt rules:
- Default to `"expense"` when in doubt
- For `"split_change"`, only return it if both percentages can be confidently extracted and summed to ~100
- For `"balance"`, always return year+month (defaults to current date if not mentioned)
- Sender name is provided so "yo quiero pagar el 70%" can be resolved

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
- Shared defaults to "Si"; "no compartida" in message → "No"
- Special case: if message ends with "Total: $###", that number is the value and everything before is the concept

### `extract_month(text, current_date) → tuple[int, int]`

Fallback only — called by `handle_balance()` if `classify_intent` didn't return year+month. Returns `(year, month)`.

---

## Database Schema

### Table: `expenses`

```sql
CREATE TABLE IF NOT EXISTS expenses (
    id            SERIAL PRIMARY KEY,
    fecha         DATE         NOT NULL,
    quien_pago    VARCHAR(3)   NOT NULL,   -- 'Aru' | 'Mon'
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,   -- COP, integer
    compartida    VARCHAR(2)   NOT NULL,   -- 'Si' | 'No'
    valor_a_pagar NUMERIC(12,2),          -- amount owed by the other person
    observacion   TEXT,                    -- 'Aru Debe' | 'Mon Debe' | '{payer} Debe'
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
- If **not shared** → payer is owed the full amount; `observacion = "{payer} Debe"`

### `compute_balance(expenses) → dict`

Aggregates a list of expense dicts into:
```python
{
  "mes": "Abril",
  "gastos_totales": 1200000,
  "aron_gasto": 800000,
  "mon_gasto": 400000,
  "aron_debe": 148000.0,     # sum of valor_a_pagar where observacion == "Aru Debe"
  "mon_debe": 504000.0,      # sum of valor_a_pagar where observacion == "Mon Debe"
  "balance_key": "Mon debe a Aron",
  "deuda_total": 356000.0,   # abs(aron_debe - mon_debe)
  "por_categoria": {"ALIMENTACIÓN": 450000, ...}
}
```

---

## Google Sheets Integration (`sheets.py`)

### Authentication

Uses a Google Cloud **service account** JSON file. Path is read from `GOOGLE_SERVICE_ACCOUNT_JSON` env var. The file is mounted read-only into the container from `./credentials/`.

Required OAuth scope: `https://www.googleapis.com/auth/spreadsheets`

### `export_month_to_sheet(year, month, expenses) → str`

1. Opens the spreadsheet by `GOOGLE_SHEET_ID`
2. Resolves tab name: `f"{MONTH_ABBR_ES[month]} {year}"` — e.g. `"ABR 2026"`
3. Clears the tab if it exists; creates it if it doesn't
4. Writes header row + one row per expense (10 columns)
5. Returns `https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}`

Column order in the sheet: `id, fecha, quien_pago, subcategoria, categoria, concepto, valor, compartida, valor_a_pagar, observacion`

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
      pg_isready — bot waits for this before starting

  bot:
    build: .                                       # from Dockerfile (python:3.12-slim)
    depends_on: db (service_healthy)
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./credentials:/app/credentials:ro          # service account JSON

volumes:
  postgres_data:
```

---

## Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `TELEGRAM_TOKEN` | Yes | — | From @BotFather |
| `OPENAI_API_KEY` | Yes | — | |
| `LLM_MODEL` | No | `gpt-4.1-nano` | Swap model without code change |
| `POSTGRES_HOST` | No | `localhost` | Use `db` in Docker Compose |
| `POSTGRES_PORT` | No | `5432` | |
| `POSTGRES_DB` | No | `finbot` | |
| `POSTGRES_USER` | No | `finbot` | |
| `POSTGRES_PASSWORD` | Yes | — | |
| `GOOGLE_SHEET_ID` | Yes | — | From spreadsheet URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | — | Use `/app/credentials/service_account.json` in Docker |

---

## Deployment

### Local

```bash
cp .env.example .env
# edit .env with real values
# place credentials/service_account.json
docker compose up
```

### VPS

```bash
git clone <repo> finbot && cd finbot
cp .env.example .env && nano .env
# upload credentials/service_account.json via scp or similar
docker compose up -d
```

Data persists in the `postgres_data` Docker volume across restarts and image rebuilds.

---

## Google Sheets One-Time Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project
2. Enable **Google Sheets API**
3. Create a **Service Account** → Actions → Manage keys → Add key → JSON
4. Save the downloaded JSON to `./credentials/service_account.json`
5. Create a Google Spreadsheet; share it with the service account email (editor)
6. Copy the spreadsheet ID from its URL (the long string between `/d/` and `/edit`)
7. Set `GOOGLE_SHEET_ID=<that ID>` in `.env`

---

## Adding a New Intent

1. **`llm.py → _CLASSIFIER_SYSTEM`** — add the new intent name, its description, and the params it should return
2. **`handlers/`** — create `handlers/your_feature.py` with an async handler function
3. **`bot.py → dispatch()`** — add `elif intent == "your_intent": await your_handler(...)` and import it
4. If the handler needs a Telegram command shortcut, register it with `app.add_handler(CommandHandler("cmd", fn))`
