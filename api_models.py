from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    fecha: str
    quien_pago: str
    subcategoria: str = ""
    categoria: str = ""
    concepto: str
    valor: int
    compartida: str = "No"


class ExpenseResponse(BaseModel):
    id: int
    fecha: str
    quien_pago: str
    subcategoria: str | None = None
    categoria: str | None = None
    concepto: str
    valor: int
    compartida: str
    valor_a_pagar: float | None = None
    observacion: str | None = None


class PersonalBalance(BaseModel):
    viewer: str
    viewer_gasto: int
    gastos_totales: int
    por_categoria: dict[str, int]


class SharedBalance(BaseModel):
    aron_gasto: int
    mon_gasto: int
    gastos_totales: int
    aron_debe: float
    mon_debe: float
    balance_key: str
    deuda_total: float
    por_categoria: dict[str, int]


class BalanceResponse(BaseModel):
    mes: str
    personal: PersonalBalance
    compartido: SharedBalance


class SplitResponse(BaseModel):
    split_aru: float
    split_mon: float


class SplitUpdate(BaseModel):
    split_aru: float
    split_mon: float


class HealthResponse(BaseModel):
    status: str
