import logging
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import API_CORS_ORIGINS
import api_auth
import api_models
import finance
import database

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FinBot API", version="1.0.0")

origins = [o.strip() for o in API_CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=api_models.HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/api/expenses", response_model=list[api_models.ExpenseResponse])
def list_expenses(
    year: int = Query(...),
    month: int = Query(...),
    user: str = Depends(api_auth.get_current_user),
):
    expenses = database.get_expenses_by_month(year, month)
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
            "observacion": e.get("observacion"),
        }
        for e in expenses
    ]


@app.post("/api/expenses", response_model=api_models.ExpenseResponse, status_code=201)
def create_expense(
    expense: api_models.ExpenseCreate,
    user: str = Depends(api_auth.get_current_user),
):
    split_aru, split_mon = database.get_split()
    data = expense.model_dump()
    data = finance.compute_split(data, split_aru, split_mon)
    row_id = database.insert_expense(data)
    return {"id": row_id, **data, "fecha": str(data["fecha"])}


@app.put("/api/expenses/{expense_id}", response_model=api_models.ExpenseResponse)
def update_expense(
    expense_id: int,
    body: api_models.ExpenseUpdate,
    user: str = Depends(api_auth.get_current_user),
):
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    merged = dict(existing)
    merged.update(fields)

    needs_split = {"valor", "compartida", "quien_pago"} & set(fields.keys())
    if needs_split:
        split_aru, split_mon = database.get_split()
        merged = finance.compute_split(merged, split_aru, split_mon)
        fields["valor_a_pagar"] = merged["valor_a_pagar"]
        fields["observacion"] = merged["observacion"]

    database.update_expense(expense_id, fields)
    updated = database.get_expense_by_id(expense_id)
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
        "observacion": updated.get("observacion"),
    }


@app.delete("/api/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    user: str = Depends(api_auth.get_current_user),
):
    existing = database.get_expense_by_id(expense_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    database.delete_expense(expense_id)
    return {"deleted": True, "id": expense_id}


@app.get("/api/balance", response_model=api_models.BalanceResponse)
def get_balance(
    year: int = Query(...),
    month: int = Query(...),
    user: str = Depends(api_auth.get_current_user),
):
    expenses = database.get_expenses_by_month(year, month)
    if not expenses:
        return {
            "mes": "",
            "personal": {
                "viewer": user,
                "viewer_gasto": 0,
                "gastos_totales": 0,
                "por_categoria": {},
            },
            "compartido": {
                "aron_gasto": 0,
                "mon_gasto": 0,
                "gastos_totales": 0,
                "aron_debe": 0,
                "mon_debe": 0,
                "balance_key": "Pagaron lo mismo",
                "deuda_total": 0,
                "por_categoria": {},
            },
        }
    return finance.compute_balance(expenses, viewer=user)


@app.get("/api/settings/split", response_model=api_models.SplitResponse)
def get_split(user: str = Depends(api_auth.get_current_user)):
    aru, mon = database.get_split()
    return {"split_aru": aru, "split_mon": mon}


@app.put("/api/settings/split", response_model=api_models.SplitResponse)
def update_split(
    body: api_models.SplitUpdate,
    user: str = Depends(api_auth.get_current_user),
):
    if abs(body.split_aru + body.split_mon - 100) > 0.01:
        raise HTTPException(status_code=400, detail="Los porcentajes deben sumar 100")
    database.set_setting("split_aru", str(body.split_aru / 100))
    database.set_setting("split_mon", str(body.split_mon / 100))
    return {"split_aru": body.split_aru / 100, "split_mon": body.split_mon / 100}
