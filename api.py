import logging
import httpx
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import API_CORS_ORIGINS, TELEGRAM_TOKEN
import api_auth
import api_models
import finance
import database

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FinDuo API", version="4.0.0")

origins = [o.strip() for o in API_CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIELD_LABELS = {
    "fecha": "📅 Fecha",
    "quien_pago": "👤 Quien pagó",
    "subcategoria": "🏷 SubCategoría",
    "categoria": "📂 Categoría",
    "concepto": "📝 Concepto",
    "valor": "💰 Valor",
    "compartida": "🤝 Compartida",
}


async def _notify_telegram(chat_id: int, text: str):
    """Send message via Telegram Bot API."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
    except Exception:
        logger.warning("Could not send Telegram notification to %s", chat_id)


def _fmt_val(field: str, val) -> str:
    if field == "valor":
        return f"${int(val):,}"
    return str(val)


def _build_diff(before: dict, after: dict, changed_keys: set[str]) -> str:
    lines = []
    for key in changed_keys:
        label = _FIELD_LABELS.get(key, key)
        old_val = _fmt_val(key, before.get(key, ""))
        new_val = _fmt_val(key, after.get(key, ""))
        lines.append(f"{label}: {old_val} → {new_val}")
    return "\n".join(lines)


@app.get("/api/health", response_model=api_models.HealthResponse)
def health():
    return {"status": "ok"}


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=api_models.TokenResponse, status_code=201)
def register(body: api_models.UserRegister):
    existing = database.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    password_hash = api_auth.hash_password(body.password)
    couple_id = database.create_couple()
    user_id = database.create_user(
        email=body.email,
        password_hash=password_hash,
        display_name=body.display_name,
        couple_id=couple_id,
    )

    token = api_auth.create_token(user_id)
    return {"access_token": token}


@app.post("/api/auth/login", response_model=api_models.TokenResponse)
def login(body: api_models.UserLogin):
    user = database.get_user_by_email(body.email)
    if not user or not api_auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = api_auth.create_token(user["id"])
    return {"access_token": token}


@app.post("/api/auth/join", response_model=api_models.UserResponse)
def join_couple(
    body: api_models.JoinRequest,
    user: dict = Depends(api_auth.get_current_user),
):
    # If user is already in a couple, leave it first
    if user.get("couple_id"):
        database.leave_couple(user["id"])

    success = database.join_couple(user["id"], body.invite_code)
    if not success:
        raise HTTPException(status_code=404, detail="Código de invitación inválido")

    updated = database.get_user_by_id(user["id"])
    couple = database.get_couple_by_id(updated["couple_id"]) if updated.get("couple_id") else None
    updated["invite_code"] = couple["invite_code"] if couple else None
    return updated


@app.get("/api/auth/me", response_model=api_models.UserResponse)
def get_me(user: dict = Depends(api_auth.get_current_user)):
    if user.get("couple_id"):
        couple = database.get_couple_by_id(user["couple_id"])
        user["invite_code"] = couple["invite_code"] if couple else None

    user["created_at"] = str(user.get("created_at", ""))
    user["status_updated_at"] = str(user.get("status_updated_at")) if user.get("status_updated_at") else None
    return user


@app.get("/api/auth/couple/members", response_model=list[api_models.CoupleMember])
def get_couple_members(user: dict = Depends(api_auth.get_current_user)):
    if not user.get("couple_id"):
        raise HTTPException(status_code=400, detail="No perteneces a una pareja")
    members = database.get_couple_users(user["couple_id"])
    return [{"id": m["id"], "display_name": m["display_name"], "email": m["email"]} for m in members]


# ── Couple Lifecycle Endpoints ────────────────────────────────────────────────

@app.post("/api/couple/leave", response_model=api_models.UserResponse)
async def leave_couple_endpoint(user: dict = Depends(api_auth.get_current_user)):
    if not user.get("couple_id"):
        raise HTTPException(status_code=400, detail="No estás en una pareja")

    # Get partner before leaving (for notification)
    partner = database.get_partner(user["id"])

    # Leave couple — both users are marked as left immediately
    success = database.leave_couple(user["id"])
    if not success:
        raise HTTPException(status_code=400, detail="No se pudo salir de la pareja")

    # Notify partner via Telegram (if they have chat_id)
    if partner and partner.get("chat_id"):
        await _notify_telegram(
            partner["chat_id"],
            f"👋 {user['display_name']} ha dejado la pareja financiera.\n"
            f"Ya no pueden compartir gastos. Podés invitar a otra persona desde la web."
        )

    # Return updated user
    updated = database.get_user_by_id(user["id"])
    return updated


@app.get("/api/couples/history", response_model=list[api_models.CoupleHistory])
def get_couple_history(user: dict = Depends(api_auth.get_current_user)):
    couples = database.get_user_couples(user["id"])
    return [
        {
            "couple_id": c["couple_id"],
            "partner_name": c["partner_name"],
            "joined_at": str(c["joined_at"]),
            "left_at": str(c["left_at"]) if c.get("left_at") else None,
            "total_spent": c["total_spent"],
            "is_active": c["is_active"],
        }
        for c in couples
    ]


@app.get("/api/couples/{couple_id}/expenses", response_model=list[api_models.ExpenseResponse])
def get_couple_expenses_endpoint(
    couple_id: int,
    year: int = Query(None),
    month: int = Query(None),
    user: dict = Depends(api_auth.get_current_user),
):
    # Verify user belongs (or belonged) to this couple
    user_couples = database.get_user_couples(user["id"])
    valid_ids = {c["couple_id"] for c in user_couples}
    if couple_id not in valid_ids:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta pareja")

    expenses = database.get_couple_expenses(couple_id)

    # Filter by year/month if provided
    if year and month:
        expenses = [
            e for e in expenses
            if e["fecha"].year == year and e["fecha"].month == month
        ]

    return [
        {
            "id": e["id"],
            "fecha": str(e["fecha"]),
            "quien_pago": e["quien_pago"],
            "subcategoria": e.get("subcategoria"),
            "categoria": e.get("categoria"),
            "concepto": e["concepto"],
            "valor": e["valor"],
            "compartida": e["compartida"],
            "valor_a_pagar": float(e["valor_a_pagar"]) if e.get("valor_a_pagar") else None,
        }
        for e in expenses
    ]


# ── Expense Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/expenses", response_model=list[api_models.ExpenseResponse])
def list_expenses(
    year: int = Query(...),
    month: int = Query(...),
    user: dict = Depends(api_auth.get_current_user),
):
    if not user.get("couple_id"):
        return []

    couple_users = database.get_couple_users(user["couple_id"])
    user_ids = [u["id"] for u in couple_users]
    expenses = database.get_expenses_by_month_and_users(year, month, user_ids, user["couple_id"])
    return [
        {
            "id": e["id"],
            "fecha": str(e["fecha"]),
            "quien_pago": e["quien_pago"],
            "subcategoria": e.get("subcategoria"),
            "categoria": e.get("categoria"),
            "concepto": e["concepto"],
            "valor": e["valor"],
            "compartida": e["compartida"],
            "valor_a_pagar": float(e["valor_a_pagar"]) if e.get("valor_a_pagar") else None,
        }
        for e in expenses
    ]


@app.post("/api/expenses", response_model=api_models.ExpenseResponse, status_code=201)
async def create_expense(
    expense: api_models.ExpenseCreate,
    user: dict = Depends(api_auth.get_current_user),
):
    if not user.get("couple_id"):
        raise HTTPException(status_code=400, detail="No estás en una pareja")

    couple_users = database.get_couple_users(user["couple_id"])
    users_dict = {u["id"]: u["display_name"] for u in couple_users}
    splits = database.get_split_for_couple(user["couple_id"])

    data = expense.model_dump()
    data["couple_id"] = user["couple_id"]  # Link expense to couple

    payer_user = next((u for u in couple_users if u["display_name"] == data.get("quien_pago")), None)
    if payer_user:
        data["quien_pago_id"] = payer_user["id"]

    if splits and users_dict:
        data = finance.compute_split(data, splits, users_dict)
    else:
        data.setdefault("valor_a_pagar", data["valor"])

    row_id = database.insert_expense(data)

    if data.get("compartida") == "Si":
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            await _notify_telegram(
                partner["chat_id"],
                f"⚠️ {user['display_name']} ha registrado un gasto compartido:\n"
                f"#{row_id} — {data.get('concepto', '')} — ${int(data['valor']):,} ({data.get('quien_pago', '')}, {data.get('fecha', '')})"
            )

    return {"id": row_id, **data, "fecha": str(data["fecha"])}


@app.put("/api/expenses/{expense_id}", response_model=api_models.ExpenseResponse)
async def update_expense(
    expense_id: int,
    body: api_models.ExpenseUpdate,
    user: dict = Depends(api_auth.get_current_user),
):
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    # Verify expense belongs to user's active couple
    if existing.get("couple_id") != user.get("couple_id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a este gasto")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    if "quien_pago" in fields:
        couple_users = database.get_couple_users(user["couple_id"])
        payer_user = next((u for u in couple_users if u["display_name"] == fields["quien_pago"]), None)
        if payer_user:
            fields["quien_pago_id"] = payer_user["id"]

    merged = dict(existing)
    merged.update(fields)

    needs_split = {"valor", "compartida", "quien_pago"} & set(fields.keys())
    if needs_split:
        couple_users = database.get_couple_users(user["couple_id"])
        users_dict = {u["id"]: u["display_name"] for u in couple_users}
        splits = database.get_split_for_couple(user["couple_id"])
        if splits and users_dict:
            merged = finance.compute_split(merged, splits, users_dict)
            fields["valor_a_pagar"] = merged["valor_a_pagar"]
            if "debt_user_id" in merged:
                fields["debt_user_id"] = merged["debt_user_id"]

    database.update_expense(expense_id, fields)
    updated = database.get_expense_by_id(expense_id)

    shared_before = existing.get("compartida", "No") == "Si"
    shared_after = (merged.get("compartida") or existing.get("compartida", "No")) == "Si"
    if shared_before or shared_after:
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            changed_keys = set(fields.keys()) & {"valor", "concepto", "fecha", "compartida", "quien_pago", "categoria", "subcategoria"}
            diff = _build_diff(
                {k: existing.get(k) for k in changed_keys},
                {k: merged.get(k, existing.get(k)) for k in changed_keys},
                changed_keys,
            )
            await _notify_telegram(
                partner["chat_id"],
                f"⚠️ {user['display_name']} ha editado un gasto compartido #{expense_id}:\n{diff}"
            )

    return {
        "id": updated["id"],
        "fecha": str(updated["fecha"]),
        "quien_pago": updated["quien_pago"],
        "subcategoria": updated.get("subcategoria"),
        "categoria": updated.get("categoria"),
        "concepto": updated["concepto"],
        "valor": updated["valor"],
        "compartida": updated["compartida"],
        "valor_a_pagar": float(updated["valor_a_pagar"]) if updated.get("valor_a_pagar") else None,
    }


@app.delete("/api/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    user: dict = Depends(api_auth.get_current_user),
):
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    # Verify expense belongs to user's active couple
    if existing.get("couple_id") != user.get("couple_id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a este gasto")

    database.delete_expense(expense_id)

    if existing.get("compartida") == "Si":
        partner = database.get_partner(user["id"])
        if partner and partner.get("chat_id"):
            concepto = existing.get("concepto", "")
            valor = int(existing["valor"])
            fecha = str(existing["fecha"])
            await _notify_telegram(
                partner["chat_id"],
                f"⚠️ {user['display_name']} ha eliminado un gasto compartido:\n"
                f"#{expense_id} — {concepto} — ${valor:,} ({fecha})"
            )

    return {"deleted": True, "id": expense_id}


# ── Income Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/incomes", response_model=list[api_models.IncomeResponse])
def list_incomes(
    year: int = Query(...),
    month: int = Query(...),
    user: dict = Depends(api_auth.get_current_user),
):
    incomes = database.get_incomes_by_month(year, month, user["id"])
    return [
        {
            "id": i["id"],
            "fecha": str(i["fecha"]),
            "concepto": i["concepto"],
            "valor": i["valor"],
            "user_id": i["user_id"],
            "created_at": str(i["created_at"]),
        }
        for i in incomes
    ]


@app.post("/api/incomes", response_model=api_models.IncomeResponse, status_code=201)
def create_income(
    body: api_models.IncomeCreate,
    user: dict = Depends(api_auth.get_current_user),
):
    data = body.model_dump()
    data["user_id"] = user["id"]
    row_id = database.insert_income(data)
    return {"id": row_id, **data, "created_at": ""}


@app.put("/api/incomes/{income_id}", response_model=api_models.IncomeResponse)
def update_income(
    income_id: int,
    body: api_models.IncomeUpdate,
    user: dict = Depends(api_auth.get_current_user),
):
    existing = database.get_income_by_id(income_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")

    if existing.get("user_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a este ingreso")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    database.update_income(income_id, fields)
    updated = database.get_income_by_id(income_id)
    return {
        "id": updated["id"],
        "fecha": str(updated["fecha"]),
        "concepto": updated["concepto"],
        "valor": updated["valor"],
        "user_id": updated["user_id"],
        "created_at": str(updated["created_at"]),
    }


@app.delete("/api/incomes/{income_id}")
def delete_income(
    income_id: int,
    user: dict = Depends(api_auth.get_current_user),
):
    existing = database.get_income_by_id(income_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")

    if existing.get("user_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a este ingreso")

    database.delete_income(income_id)
    return {"deleted": True, "id": income_id}


# ── Balance & Settings ────────────────────────────────────────────────────────

@app.get("/api/balance", response_model=api_models.BalanceResponse)
def get_balance(
    year: int = Query(...),
    month: int = Query(...),
    user: dict = Depends(api_auth.get_current_user),
):
    if not user.get("couple_id"):
        raise HTTPException(status_code=400, detail="No estás en una pareja")

    couple_users = database.get_couple_users(user["couple_id"])
    user_ids = [u["id"] for u in couple_users]
    users_dict = {u["id"]: u["display_name"] for u in couple_users}

    expenses = database.get_expenses_by_month_and_users(year, month, user_ids, user["couple_id"])
    if not expenses:
        return {
            "mes": "",
            "personal": {
                "viewer_id": user["id"],
                "viewer_name": user["display_name"],
                "viewer_gasto": 0,
                "gastos_totales": 0,
                "por_categoria": {},
            },
            "compartido": {
                "gastos": [0] * len(user_ids),
                "deudas": [0.0] * len(user_ids),
                "gastos_totales": 0,
                "balance_key": "Pagaron lo mismo",
                "deuda_total": 0,
                "por_categoria": {},
            },
        }
    return finance.compute_balance(expenses, viewer_id=user["id"], users=users_dict)


@app.get("/api/settings/split", response_model=api_models.SplitResponse)
def get_split(user: dict = Depends(api_auth.get_current_user)):
    splits = database.get_split_for_couple(user["couple_id"])
    return {"splits": splits}


@app.put("/api/settings/split", response_model=api_models.SplitResponse)
def update_split(
    body: api_models.SplitUpdate,
    user: dict = Depends(api_auth.get_current_user),
):
    total = sum(body.splits.values())
    if abs(total - 1.0) > 0.001:
        raise HTTPException(status_code=400, detail="Los porcentajes deben sumar 1.0")

    database.update_split_for_couple(user["couple_id"], body.splits)
    return {"splits": body.splits}
