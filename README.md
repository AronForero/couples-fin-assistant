# FinDuo

A personal finance Telegram bot for Aron (Aru) and Monica (Mon). Send expenses in plain text and get monthly balance summaries — no spreadsheets, no manual tracking.

Built with Python, runs via Telegram polling (no SSL certificate required), stores data in PostgreSQL, and is fully containerised with Docker Compose for local or VPS deployment.

---

## How It Works

You send a message to the bot like `"Supermercado 50000"`. The bot uses an LLM to extract the concept, value, date, and payer, categorises the expense, calculates who owes what, saves it to the database, and confirms to both users. That's it.

---

## Usage

### Registering an expense

Just send the concept and the value in any order. The bot figures out the rest.

```
Supermercado 50000
crepes&waffles 120000
Gasolina 80000 Aru
Cine 30000 no compartida
Mon pagó vegetales 20000, proteínas 100000. Total: $120000
```

**What the bot infers automatically:**
- **Payer** — from who sent the message, or from an explicit mention of `Aru` or `Mon`
- **Date** — from the message timestamp, or from a date mentioned in the text (e.g. `"ayer"`, `"01/07"`)
- **Shared** — `Si` by default; add `"no compartida"` to mark it as personal
- **Category & subcategory** — inferred from the concept text

After saving, both users receive a confirmation:

```
✅ Gasto registrado en la base de datos:
📅 Fecha: 2026-04-24
👤 Quien pagó: Aru
🏷 SubCategoría: Restaurantes
📂 Categoría: ALIMENTACIÓN
📝 Concepto: crepes&waffles
💰 Valor: $120,000
🤝 Compartida: Si
💸 Valor a pagar: $44,400
📌 Observación: Mon Debe
```

### Checking the balance

Send `Balance` to get the current month's summary. Add a month name or number to query a specific month:

```
Balance
Balance marzo
Balance 03
```

The bot replies with:

```
📊 Resumen de Gastos — Abril 📊

Gastos totales del mes: $1,200,000

💸 Quién gastó:
  Aron gastó: $800,000
  Mon gastó:  $400,000

⚖️ Saldo pendiente:
  Aron debe: $148,000
  Mon debe:  $504,000

¡Mon debe a Aron: $356,000! 😬

📂 Gastos por categoría:
  ALIMENTACIÓN: $450,000
  VIVIENDA: $600,000
  TRANSPORTE: $150,000
```

Below the message a **📊 Ver en Google Sheets** button exports the month's data to the shared Google Spreadsheet and returns a link.

---

## Expense Categories

| Category | Subcategories |
|---|---|
| ALIMENTACIÓN | Supermercados, Mercado Plaza, Restaurantes |
| TRANSPORTE | Gasolina Carro, Transp. Público |
| VIVIENDA | Arriendo + Admin, Servicios Públicos, Internet, Servicios Técnicos Hogar, Lencería Hogar, Activos Fijos Hogar |
| SALUD | AtenciónMéd. Complementaria, Exámenes Médicos, Medicina y Suplementos |
| EDUCACIÓN | Formación Académica, Libros + E-Learning |
| ENTRETENIMIENTO | Actividades Outside, Plataformas Streaming |
| INTERESES | Pago Intereses |
| AHORRO/INVERSIÓN | Ahorro Pareja |
| IMPREVISTOS | Obsequios, Otros |

---

## Expense Split

Shared expenses are divided between Aru and Mon using a fixed percentage:

- **Aru owes 63%** of any shared expense paid by Mon
- **Mon owes 37%** of any shared expense paid by Aru

The percentages are configurable via the `/split` command (V2).

---

## Access Control

Only two Telegram user IDs are authorised:

| User | ID |
|---|---|
| Aron (Aru) | `247795192` |
| Monica (Mon) | `1560352087` |

All other users are silently ignored.

---

## Account Status

When you register, you get a 30-day free trial. After that, you need a paid account to keep using the bot.

- **Trial** — Yellow banner in the dashboard: *"Modo de prueba — X días restantes"*. Full access to everything.
- **Active** — Paid account. Full access.
- **Suspended** — Coral banner in the dashboard: *"Tu cuenta está suspendida. Completa tu pago para continuar."*
  - The Telegram bot will reject all commands.
  - The dashboard still works for viewing your data, but you can't make changes.

> Payment integration is not implemented yet. Status changes will be made automatically once payments are integrated.

---

## Tracking Income

You can also record money you receive — salary, freelance work, profits from a side business, etc. Income tracking is personal (not shared with your partner).

Send the bot a message with an income keyword and a value:

```
Salario 2000000
Ingreso freelance 1500000
Recibí utilidades panaderia 3500000
Cobré venta de bicicleta 800000
```

Income keywords the bot understands: *salario, ingreso, ingresos, recibí, gané, cobré, utilidades, honorarios, freelance, venta, pago recibido*.

After saving, you'll get a confirmation like:

```
✅ Ingreso #5 registrado:
📅 Fecha: 2026-06-07
👤 Recibido por: Aru
📝 Concepto: Salario
💰 Valor: $2,000,000
```

You can also edit and delete incomes from the bot, just like expenses — for example: *"editar ingreso 5, el valor era 2500000"* or *"borrar ingreso 5"*.

> Income calculations (your actual money after subtracting expenses) are coming in a later version. For now, the dashboard just shows the list.

### Dashboard transactions page

The **Gastos** page has been renamed to **Transacciones** and now shows both expenses and incomes in the same list. Use the filter at the top to switch between:

- **Todos** — default, shows both
- **Gastos** — only expenses
- **Ingresos** — only incomes

Income rows are highlighted in green with a "+" sign so you can spot them at a glance. The page also shows two summary cards: total expenses and total incomes for the selected month.

---

## Project Structure

```
finduo/
├── bot.py                  # Entry point — Telegram app + polling
├── config.py               # Environment variables and constants
├── database.py             # PostgreSQL init, CRUD, CSV export
├── llm.py                  # LLM expense parsing and month extraction
├── finance.py              # Split calculation and balance aggregation
├── api.py                  # FastAPI dashboard backend (V4)
├── api_auth.py             # JWT auth + password hashing
├── api_models.py           # Pydantic models for API
├── sheets.py               # Google Sheets export (V2)
├── handlers/
│   ├── expense.py          # AddExpense flow
│   ├── income.py           # AddIncome flow (V7)
│   ├── balance.py          # Balance + sheet export callback
│   ├── recent.py           # Recent expenses list
│   ├── edit.py             # Edit expense or income (V7)
│   ├── delete.py           # Delete expense or income (V7)
│   ├── settings.py         # /split command (V2)
│   ├── chat.py             # Conversational fallback
│   └── link.py             # /link email command
├── couples-fin-dashboard/  # Next.js web dashboard
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── version/
    ├── mvp.md
    ├── version-2.md
    ├── version-3.md
    ├── version-4.1-schema.md
    ├── version-4.2-auth.md
    ├── version-4.3a-finance-llm.md
    ├── version-4.3b-handlers-bot-api.md
    ├── version-4.4-notifications.md
    ├── version-5.1-soft-delete-schema.md
    ├── version-5.2-soft-delete-api.md
    ├── version-5.3-soft-delete-bot.md
    └── version-5.4-soft-delete-frontend.md
```

---

## Setup & Deployment

### Prerequisites

- Docker and Docker Compose installed
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- An LLM provider API key (e.g. OpenRouter, OpenAI, Groq)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
TELEGRAM_TOKEN=your_telegram_bot_token_here

LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4.1

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=finduo
POSTGRES_USER=finduo
POSTGRES_PASSWORD=change_me_in_production
```

### 2. Set up Google Sheets export (V2)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Sheets API**.
3. Create a **Service Account**, then generate and download its JSON key.
4. Place the JSON file at `./credentials/service_account.json` (this folder is gitignored).
5. Create a Google Spreadsheet and share it with the service account email (editor access).
6. Copy the spreadsheet ID from its URL into `GOOGLE_SHEET_ID` in your `.env`.

> The `credentials/` folder is mounted read-only into the container via the Docker volume defined in `docker-compose.yml`.

### 3. Run locally

```bash
docker compose up
```

The bot starts polling immediately. No webhook or SSL certificate needed.

### 4. Deploy to a VPS

```bash
# On your server
git clone <repo-url> finduo
cd finduo
cp .env.example .env
# edit .env with your values
docker compose up -d
```

Data is persisted in a named Docker volume (`postgres_data`) and survives container restarts and upgrades.

---

## Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_TOKEN` | Bot token from @BotFather | — |
| `LLM_API_KEY` | API key for your LLM provider | — |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model name | `openai/gpt-4.1` |
| `POSTGRES_HOST` | Database host | `db` (Docker service name) |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `finduo` |
| `POSTGRES_USER` | Database user | `finduo` |
| `POSTGRES_PASSWORD` | Database password | — |
| `GOOGLE_SHEET_ID` | Target spreadsheet ID (V2) | — |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to service account JSON (V2) | `/app/credentials/service_account.json` |

---

## Database Schema

```sql
CREATE TABLE expenses (
    id            SERIAL PRIMARY KEY,
    fecha         DATE         NOT NULL,
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,
    compartida    VARCHAR(2)   NOT NULL,   -- 'Si' | 'No'
    valor_a_pagar NUMERIC(12,2),
    quien_pago_id INTEGER      REFERENCES users(id),
    debt_user_id  INTEGER      REFERENCES users(id),
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
```

Month is derived at query time (`EXTRACT(MONTH FROM fecha)`), not stored separately.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Telegram | `python-telegram-bot` v21 (polling) |
| Database | PostgreSQL 16 |
| LLM | Configurable provider (OpenRouter, OpenAI, Groq, etc.) |
| Containerisation | Docker + Docker Compose |

---

## Error Handling

| Situation | Bot response |
|---|---|
| Message with no concept or value | Spanish help message with usage example |
| Database write failure | Generic error message; exception logged |
| Unauthorised user | Silent ignore |
| Unknown intent | Treated as expense attempt; falls back to help message if parsing fails |

---

## Roadmap

| Version | Feature | Status |
|---|---|---|
| **V1** | Expense registration, balance query, CSV export, access control | ✅ |
| **V2** | Dynamic split percentage via `/split` command, Google Sheets link export | ✅ |
| **V3** | Personal expense layer — private per-user expenses, personal balance, private Google Sheet per person | ✅ |
| **V4** | Web dashboard with JWT auth, per-user accounts, couple invite via web | ✅ |
| **V5** | Couple lifecycle — leave couple, view history, expenses linked to specific couples | ✅ |
| **V6** | User account status — 30-day trial, active, suspended; bot blocked when suspended; dashboard read-only | ✅ |
| **V7** | Income feature — record salary, freelance, etc. via bot; dashboard filter for expenses vs incomes | ✅ |

See the `version/` directory for detailed specs of each version.
