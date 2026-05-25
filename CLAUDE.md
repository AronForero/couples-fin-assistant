# FinDuo — Claude Code Context

This file helps Claude Code resume work on this project without re-reading every source file.

## Project Summary

A personal finance Telegram bot for Aron (Aru) and Monica (Mon). Users send free-text expense messages and balance queries; the bot uses an LLM to understand them, stores data in PostgreSQL, and exports to Google Sheets on request. Currently at **V2**.

## Current Version

**V2 is fully implemented and on disk.** V3 is specced in `version/version-3.md` but not yet built.

| Version | Status | Key addition |
|---|---|---|
| V1 | Done | Expense registration, balance query, CSV export |
| V2 | Done | Dynamic split via conversational NLU + `/split`; Google Sheets link export instead of CSV |
| V3 | Planned | Personal vs couples expense distinction; per-user private Google Sheet |

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Telegram | `python-telegram-bot` v21 — **polling**, no SSL/webhook needed |
| Database | PostgreSQL 16 via Docker |
| LLM | Configurable provider — set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (default: OpenRouter + `openai/gpt-4.1`) |
| Sheets export | `gspread` + Google service account |
| Containerisation | Docker + Docker Compose |

## Directory Map

```
finduo/
├── bot.py                  # Entry point — Telegram app setup + run_polling()
├── config.py               # All env vars and business constants (ALLOWED_USER_IDS, USER_MAP, CATEGORIES, etc.)
├── database.py             # PostgreSQL: init, expenses CRUD, settings CRUD, get_split()
├── finance.py              # compute_split() and compute_balance() — pure functions, no I/O
├── llm.py                  # Three LLM functions: classify_intent, parse_expense, extract_month
├── sheets.py               # Google Sheets export: export_month_to_sheet()
├── handlers/
│   ├── expense.py          # handle_expense() — parse → split → save → confirm both users
│   ├── balance.py          # handle_balance() + handle_sheet_callback()
│   └── settings.py         # apply_split() + handle_split_command() (/split)
├── credentials/            # gitignored — place service_account.json here
├── docs/
│   ├── technical.md        # Developer architecture reference
│   └── features.md         # User-facing guide (Spanish, for Aru & Mon)
├── version/
│   ├── mvp.md              # V1 spec
│   ├── version-2.md        # V2 spec
│   └── version-3.md        # V3 spec (not yet implemented)
├── docker-compose.yml      # bot + db services; credentials volume mount
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Entry Point

`bot.py → main()`:
1. `database.init_db()` — creates tables and seeds default split if not present
2. Registers four handlers:
   - `/start` → `start()`
   - `/split` → `handle_split_command()` (explicit command fallback)
   - Text messages → `dispatch()`
   - Callback query `^sheet:` → `handle_sheet_callback()`
3. `app.run_polling(drop_pending_updates=True)`

## Message Flow

Every non-command text message goes through `dispatch()` in `bot.py`:

```
User message
    │
    ▼
llm.classify_intent(text, sender, date_str)
    │
    ├── intent = "balance"      → handle_balance(year, month)
    ├── intent = "split_change" → apply_split(pct_aru, pct_mon)
    └── intent = "expense"      → handle_expense()
```

`classify_intent` returns `{intent, params}` and **fails safely** to `"expense"` on any LLM error.

## Expense Pipeline

```
handle_expense()
  → llm.parse_expense()          # extracts: fecha, quien_pago, concepto, valor, compartida, categoria, subcategoria
  → database.get_split()         # reads current Aru/Mon percentages from settings table
  → finance.compute_split()      # adds: valor_a_pagar, debt_user_id
  → database.insert_expense()    # saves to expenses table
  → send confirmation to both ALLOWED_USER_IDS
```

## Balance Pipeline

```
handle_balance(year, month)       # year+month pre-extracted by classify_intent
  → database.get_expenses_by_month()
  → finance.compute_balance()     # totals by person + category, net debt
  → reply with summary + inline button "📊 Ver en Google Sheets"
  → [button tap] handle_sheet_callback()
      → sheets.export_month_to_sheet()   # writes tab "ABR 2026", returns URL
      → reply with URL
```

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

## Key Constants (config.py)

```python
ALLOWED_USER_IDS = {247795192, 1560352087}   # Aron, Monica

USER_MAP = {"aron": "Aru", "monica": "Mon", "mónica": "Mon"}

# Default split — seeded into settings table on first run; overridable at runtime via /split
# Aru owes 63% of shared expenses paid by Mon
# Mon owes 37% of shared expenses paid by Aru
```

## Database Tables

**`expenses`** — one row per registered expense:
```
id, fecha, quien_pago, subcategoria, categoria, concepto,
valor, compartida, valor_a_pagar, quien_pago_id, debt_user_id, created_at
```

**`settings`** — key/value store for runtime config:
```
key (PK), value, updated_at
--- seeded rows ---
split_aru = "0.63"
split_mon = "0.37"
```

Both tables are created idempotently in `database.init_db()`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_TOKEN` | Yes | — | From @BotFather |
| `LLM_API_KEY` | Yes | — | API key for your LLM provider |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | OpenAI-compatible base URL (OpenRouter, Together, Groq, etc.) |
| `LLM_MODEL` | No | `openai/gpt-4.1` | Model name — swap here to change provider/model |
| `POSTGRES_HOST` | No | `localhost` | Use `db` inside Docker Compose |
| `POSTGRES_PORT` | No | `5432` | |
| `POSTGRES_DB` | No | `finduo` | |
| `POSTGRES_USER` | No | `finduo` | |
| `POSTGRES_PASSWORD` | Yes | — | |
| `GOOGLE_SHEET_ID` | Yes (V2) | — | Spreadsheet ID from URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes (V2) | — | Path to service account JSON — use `/app/credentials/service_account.json` in Docker |

## How to Run Locally

```bash
cp .env.example .env    # fill in tokens and passwords
# place credentials/service_account.json
docker compose up
```

## How to Extend — Adding a New Intent

1. **`llm.py`** — add a new intent name and its params to `_CLASSIFIER_SYSTEM` prompt
2. **`handlers/`** — create a new handler function
3. **`bot.py → dispatch()`** — add a new `elif intent == "new_intent":` branch

## Next Version (V3)

V3 inverts the sharing default: expenses are **personal by default**; only marked as couples if the message contains `"compartida"` or `"con Aru/Mon"`. Personal expenses are private (only the sender sees the confirmation), stored in a separate `personal_expenses` table, and exported to a per-user private Google Sheet. Full spec: `version/version-3.md`.
