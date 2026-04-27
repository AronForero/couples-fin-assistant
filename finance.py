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


def compute_balance(expenses: list[dict]) -> dict:
    if not expenses:
        return {}

    totales = {"Aru": 0, "Mon": 0}
    aru_debe = 0.0
    mon_debe = 0.0
    cats = {cat: 0 for cat in CATEGORIES}
    cats["Otros"] = 0

    for e in expenses:
        payer = e["quien_pago"]
        valor = int(e["valor"])
        obs = e.get("observacion", "")
        vap = float(e.get("valor_a_pagar") or 0)
        cat = e.get("categoria") or ""

        totales[payer] = totales.get(payer, 0) + valor

        if obs == "Aru Debe":
            aru_debe += vap
        elif obs == "Mon Debe":
            mon_debe += vap

        if cat in cats:
            cats[cat] += valor
        else:
            cats["Otros"] += valor

    deuda = abs(aru_debe - mon_debe)
    if aru_debe > mon_debe:
        balance_key = "Aron debe a Mon"
    elif mon_debe > aru_debe:
        balance_key = "Mon debe a Aron"
    else:
        balance_key = "Pagaron lo mismo"

    first_fecha = expenses[0]["fecha"]
    if isinstance(first_fecha, str):
        month_num = int(first_fecha[5:7])
    else:
        month_num = first_fecha.month

    return {
        "mes": MONTH_NAMES_ES.get(month_num, ""),
        "gastos_totales": totales.get("Aru", 0) + totales.get("Mon", 0),
        "aron_gasto": totales.get("Aru", 0),
        "mon_gasto": totales.get("Mon", 0),
        "aron_debe": round(aru_debe, 2),
        "mon_debe": round(mon_debe, 2),
        "balance_key": balance_key,
        "deuda_total": round(deuda, 2),
        "por_categoria": cats,
    }
