# AGENTS.md — Quick Reference for OpenCode

## What This Is

A Spanish-language Telegram finance bot for two users (Aru & Mon). Free-text in, structured expense records out. Full architecture details are in `CLAUDE.md` — read that first.

## Critical Facts

- **No tests, no lint, no typecheck, no CI.** There is nothing to run to verify changes. Be careful.
- **Docker-only.** There is no local Python workflow. `docker compose up` is the only way to run.
- **LLM prompts are the behavior spec.** `llm.py` contains four system prompts that define how the bot understands messages. Changing these changes bot behavior — treat them as the most sensitive code in the repo.
- **All user-facing text is in Spanish.** UI strings, error messages, LLM prompts, categories — everything. New strings must be in Spanish.
- **No database migrations.** `database.init_db()` uses `CREATE TABLE IF NOT EXISTS`. Schema changes require manual SQL or a new migration pattern.
- **`config.SPLIT` is a dead constant.** The runtime split comes from the `settings` table via `database.get_split()`. The hardcoded `SPLIT` dict in `config.py` is not used by any pipeline.

## Documentation

- **`docs/technical.md`** — Architecture, flows, schemas, API endpoints. Update this when changing the flow, architecture, database schema, or internal logic.
- **`docs/features.md`** — User-facing feature guide (non-technical, Spanish). Update this when adding new features or modifying existing behavior. Written to explain what the bot can and cannot do — keep it clear and commercial, not technical.

## How to Run

```bash
docker compose up          # starts PostgreSQL + bot
docker compose up --build  # rebuild after code changes
docker compose down -v     # destroy DB volume (fresh start)
```

Requires a `.env` file (copy from `.env.example`).

## Where Behavior Lives

| What to change | File | Notes |
|---|---|---|
| Bot intent recognition | `llm.py` → `_CLASSIFIER_SYSTEM` | Seven intents: `balance`, `split_change`, `expense`, `chat`, `recent`, `edit`, `delete` |
| Expense parsing rules | `llm.py` → `_EXPENSE_SYSTEM` | Spanish prompt; extracts structured data from free text |
| Expense categories | `config.py` → `CATEGORIES` | Also embedded in `_EXPENSE_SYSTEM` prompt — update both |
| Split calculation | `finance.py` → `compute_split()` | Pure function; payer's share is calculated for the *other* person |
| Message routing | `bot.py` → `dispatch()` | `elif` chain on intent string |
| Adding a new intent | `llm.py` prompt + `handlers/` + `bot.py` dispatch | Three files must agree |

## Gotchas

- `parse_expense()` handles an LLM quirk where the response may be wrapped in `{"result": ...}` — see `llm.py:107`.
- `finance.compute_split()` calculates `valor_a_pagar` as what the *other* person owes, not the payer.
- `database.get_split()` reads the split from the DB every time — the default seed (`0.63`/`0.37`) only applies on first run.
- The API and bot are independent processes — they share `database.py` but never call each other.
- `CHAT_ID_TO_USER` in `config.py` maps Telegram chat IDs to user names for the `/token` command. Hardcoded — update if user IDs change.
- `ALLOWED_USER_IDS` is a `set` — order is not guaranteed when iterating for notifications.
- LLM is provider-agnostic: set `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` in `.env` to use any OpenAI-compatible provider (OpenRouter, OpenAI, Groq, Together, etc.).
