from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    fecha: str
    quien_pago: str
    subcategoria: str = ""
    categoria: str = ""
    concepto: str
    valor: int
    compartida: str = "No"


class ExpenseUpdate(BaseModel):
    fecha: str | None = None
    quien_pago: str | None = None
    subcategoria: str | None = None
    categoria: str | None = None
    concepto: str | None = None
    valor: int | None = None
    compartida: str | None = None


class ExpenseResponse(BaseModel):
    id: int
    fecha: str
    quien_pago: str
    quien_pago_id: int | None = None
    subcategoria: str | None = None
    categoria: str | None = None
    concepto: str
    valor: int
    compartida: str
    valor_a_pagar: float | None = None


class IncomeCreate(BaseModel):
    fecha: str
    concepto: str
    valor: int


class IncomeUpdate(BaseModel):
    fecha: str | None = None
    concepto: str | None = None
    valor: int | None = None


class IncomeResponse(BaseModel):
    id: int
    fecha: str
    concepto: str
    valor: int
    user_id: int
    created_at: str


class ActualMoneyResponse(BaseModel):
    total_income: int
    personal_expenses: int
    shared_expenses_my_share: int
    shared_expenses_total: int
    actual_money: int
    split_percentage: float
    period: dict


class PersonalBalance(BaseModel):
    viewer_id: int
    viewer_name: str
    viewer_gasto: int
    gastos_totales: int
    por_categoria: dict[str, int]


class SharedBalance(BaseModel):
    gastos: list[int]
    deudas: list[float]
    gastos_totales: int
    balance_key: str
    deuda_total: float
    por_categoria: dict[str, int]


class BalanceResponse(BaseModel):
    mes: str
    personal: PersonalBalance
    compartido: SharedBalance


class SplitResponse(BaseModel):
    splits: dict[int, float]


class SplitUpdate(BaseModel):
    splits: dict[int, float]


class HealthResponse(BaseModel):
    status: str


class UserRegister(BaseModel):
    email: str
    password: str
    display_name: str


class UserLogin(BaseModel):
    email: str
    password: str


class JoinRequest(BaseModel):
    invite_code: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    couple_id: int | None
    invite_code: str | None = None
    chat_id: int | None
    status: str
    status_updated_at: str | None = None
    created_at: str


class CoupleMember(BaseModel):
    id: int
    display_name: str
    email: str


class CoupleHistory(BaseModel):
    couple_id: int
    partner_name: str
    joined_at: str
    left_at: str | None  # None = still active
    total_spent: int
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
