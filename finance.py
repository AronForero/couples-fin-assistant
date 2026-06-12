from config import CATEGORIES, MONTH_NAMES_ES


def compute_split(
    expense: dict,
    splits: dict[int, float],
    users: dict[int, str],
) -> dict:
    """Compute valor_a_pagar and debt_user_id for an expense.

    Args:
        expense: dict with at least quien_pago_id, valor, compartida
        splits: {user_id: percentage} e.g. {1: 0.63, 2: 0.37}
        users: {user_id: display_name} e.g. {1: "Aru", 2: "Mon"}
    """
    expense = dict(expense)
    payer_id = expense["quien_pago_id"]
    valor = expense["valor"]

    partner_id = next(uid for uid in splits if uid != payer_id)

    if expense["compartida"] == "Si":
        expense["valor_a_pagar"] = round(valor * splits[partner_id], 2)
        expense["debt_user_id"] = partner_id
    else:
        expense["valor_a_pagar"] = valor
        expense["debt_user_id"] = payer_id

    return expense


def compute_balance(
    expenses: list[dict],
    viewer_id: int,
    users: dict[int, str],
) -> dict:
    """Compute monthly balance for a viewer.

    Args:
        expenses: list of expense dicts
        viewer_id: user ID of the person requesting the balance
        users: {user_id: display_name}
    """
    if not expenses:
        return {}

    cats_personal = {cat: 0 for cat in CATEGORIES}
    cats_personal["Otros"] = 0
    cats_shared = {cat: 0 for cat in CATEGORIES}
    cats_shared["Otros"] = 0

    viewer_gasto = 0
    gastos_por_usuario = {uid: 0 for uid in users}
    deudas_por_usuario = {uid: 0.0 for uid in users}

    for e in expenses:
        payer_id = e.get("quien_pago_id")
        valor = int(e["valor"])
        cat = e.get("categoria") or ""

        if e.get("compartida") == "Si":
            if payer_id in gastos_por_usuario:
                gastos_por_usuario[payer_id] += valor
            debt_uid = e.get("debt_user_id")
            if debt_uid and debt_uid in deudas_por_usuario:
                vap = float(e.get("valor_a_pagar") or 0)
                deudas_por_usuario[debt_uid] += vap
            if cat in cats_shared:
                cats_shared[cat] += valor
            else:
                cats_shared["Otros"] += valor
        elif payer_id == viewer_id:
            viewer_gasto += valor
            if cat in cats_personal:
                cats_personal[cat] += valor
            else:
                cats_personal["Otros"] += valor

    deuda_total = abs(deudas_por_usuario.get(viewer_id, 0) - sum(v for uid, v in deudas_por_usuario.items() if uid != viewer_id))
    deuda_total = round(sum(deudas_por_usuario.values()) / 2, 2) if any(deudas_por_usuario.values()) else 0

    if len(users) == 2:
        uid_list = list(users.keys())
        debt0 = deudas_por_usuario.get(uid_list[0], 0)
        debt1 = deudas_por_usuario.get(uid_list[1], 0)
        if debt0 > debt1:
            balance_key = f"{users[uid_list[0]]} debe a {users[uid_list[1]]}"
        elif debt1 > debt0:
            balance_key = f"{users[uid_list[1]]} debe a {users[uid_list[0]]}"
        else:
            balance_key = "Pagaron lo mismo"
        deuda_total = abs(debt0 - debt1)
    else:
        balance_key = "Balance"

    shared_total = sum(gastos_por_usuario.values())

    first_fecha = expenses[0]["fecha"]
    if isinstance(first_fecha, str):
        month_num = int(first_fecha[5:7])
    else:
        month_num = first_fecha.month

    # Build ordered arrays (sorted by user ID) — matches couple_members order
    sorted_uids = sorted(users.keys())
    gastos = [gastos_por_usuario.get(uid, 0) for uid in sorted_uids]
    deudas = [round(deudas_por_usuario.get(uid, 0), 2) for uid in sorted_uids]

    return {
        "mes": MONTH_NAMES_ES.get(month_num, ""),
        "personal": {
            "viewer_id": viewer_id,
            "viewer_name": users.get(viewer_id, ""),
            "viewer_gasto": viewer_gasto,
            "gastos_totales": viewer_gasto,
            "por_categoria": cats_personal,
        },
        "compartido": {
            "gastos": gastos,
            "deudas": deudas,
            "gastos_totales": shared_total,
            "balance_key": balance_key,
            "deuda_total": round(deuda_total, 2),
            "por_categoria": cats_shared,
        },
    }


def compute_actual_money(
    user: dict,
    incomes: list[dict],
    expenses: list[dict],
    splits: dict[int, float] | None,
) -> dict:
    """Compute user's actual money = income - personal expenses - share of shared.

    Args:
        user: the user dict (must have 'id' and optionally 'couple_id')
        incomes: list of income dicts for this user in the period
        expenses: list of expense dicts (all from the user's couple if any) in the period
        splits: {user_id: split_percentage} from get_split_for_couple, or None for solo users

    Returns dict with totals and the period.
    """
    user_id = user["id"]

    total_income = sum(int(i["valor"]) for i in incomes)

    personal_expenses = 0
    shared_total = 0

    for e in expenses:
        valor = int(e["valor"])
        if e.get("compartida") == "Si":
            shared_total += valor
        elif e.get("quien_pago_id") == user_id:
            personal_expenses += valor

    if splits and user_id in splits:
        split_pct = float(splits[user_id])
    else:
        split_pct = 0.50

    shared_my_share = round(shared_total * split_pct)

    actual_money = total_income - personal_expenses - shared_my_share

    return {
        "total_income": total_income,
        "personal_expenses": personal_expenses,
        "shared_expenses_my_share": shared_my_share,
        "shared_expenses_total": shared_total,
        "actual_money": actual_money,
        "split_percentage": split_pct,
    }


# ── Legacy wrappers (temporary, for old callers during transition) ────────────

def compute_split_legacy(expense: dict, split_aru: float, split_mon: float) -> dict:
    """For old callers during transition."""
    users = {1: "Aru", 2: "Mon"}
    splits = {1: split_aru, 2: split_mon}
    return compute_split(expense, splits, users)


def compute_balance_legacy(expenses: list[dict], viewer: str) -> dict:
    """For old callers during transition."""
    users = {1: "Aru", 2: "Mon"}
    viewer_id = next(k for k, v in users.items() if v == viewer)
    return compute_balance(expenses, viewer_id, users)
