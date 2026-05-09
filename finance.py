from config import CATEGORIES, MONTH_NAMES_ES


def compute_split(expense: dict, split_aru: float, split_mon: float) -> dict:
    expense = dict(expense)
    payer = expense["quien_pago"]
    valor = expense["valor"]

    if expense["compartida"] == "Si":
        other = "Mon" if payer == "Aru" else "Aru"
        other_pct = split_mon if payer == "Aru" else split_aru
        expense["valor_a_pagar"] = round(valor * other_pct, 2)
        expense["observacion"] = f"{other} Debe"
    else:
        expense["valor_a_pagar"] = valor
        expense["observacion"] = f"{payer} Debe"

    return expense


def compute_balance(expenses: list[dict], viewer: str) -> dict:
    if not expenses:
        return {}

    cats_personal = {cat: 0 for cat in CATEGORIES}
    cats_personal["Otros"] = 0
    cats_shared = {cat: 0 for cat in CATEGORIES}
    cats_shared["Otros"] = 0

    viewer_gasto = 0
    shared_totales = {"Aru": 0, "Mon": 0}
    aru_debe = 0.0
    mon_debe = 0.0

    for e in expenses:
        payer = e["quien_pago"]
        valor = int(e["valor"])
        cat = e.get("categoria") or ""

        if e.get("compartida") == "Si":
            shared_totales[payer] = shared_totales.get(payer, 0) + valor
            obs = e.get("observacion", "")
            vap = float(e.get("valor_a_pagar") or 0)
            if obs == "Aru Debe":
                aru_debe += vap
            elif obs == "Mon Debe":
                mon_debe += vap
            if cat in cats_shared:
                cats_shared[cat] += valor
            else:
                cats_shared["Otros"] += valor
        elif payer == viewer:
            viewer_gasto += valor
            if cat in cats_personal:
                cats_personal[cat] += valor
            else:
                cats_personal["Otros"] += valor

    deuda = abs(aru_debe - mon_debe)
    if aru_debe > mon_debe:
        balance_key = "Aron debe a Mon"
    elif mon_debe > aru_debe:
        balance_key = "Mon debe a Aron"
    else:
        balance_key = "Pagaron lo mismo"

    shared_total = shared_totales.get("Aru", 0) + shared_totales.get("Mon", 0)

    first_fecha = expenses[0]["fecha"]
    if isinstance(first_fecha, str):
        month_num = int(first_fecha[5:7])
    else:
        month_num = first_fecha.month

    return {
        "mes": MONTH_NAMES_ES.get(month_num, ""),
        "personal": {
            "viewer": viewer,
            "viewer_gasto": viewer_gasto,
            "gastos_totales": viewer_gasto,
            "por_categoria": cats_personal,
        },
        "compartido": {
            "aron_gasto": shared_totales.get("Aru", 0),
            "mon_gasto": shared_totales.get("Mon", 0),
            "gastos_totales": shared_total,
            "aron_debe": round(aru_debe, 2),
            "mon_debe": round(mon_debe, 2),
            "balance_key": balance_key,
            "deuda_total": round(deuda, 2),
            "por_categoria": cats_shared,
        },
    }
