"""
planner.py — risk profiling, auto asset allocation and goal planning.

Allocation is a heuristic based on age, investment horizon and risk appetite.
Suggestions reference real funds/stocks passed in by the caller.
"""


def risk_profile(age, horizon_years, appetite, income_stability):
    """
    age: int, horizon_years: int, appetite: 'conservative'|'moderate'|'aggressive',
    income_stability: 'stable'|'moderate'|'uncertain'
    Returns {score 0-100, label, allocation dict, explanation}
    """
    score = 50.0
    # age: younger = more risk capacity
    if age < 30:
        score += 20
    elif age < 45:
        score += 10
    elif age < 60:
        score -= 5
    else:
        score -= 15
    # appetite
    score += {"conservative": -25, "moderate": 5, "aggressive": 25}.get(appetite, 0)
    # income stability
    score += {"stable": 5, "moderate": 0, "uncertain": -15}.get(income_stability, 0)
    # horizon
    if horizon_years < 3:
        score -= 20
    elif horizon_years < 7:
        score -= 5
    else:
        score += 10

    score = max(0, min(100, score))
    if score >= 70:
        label = "Aggressive"
    elif score >= 45:
        label = "Moderate"
    else:
        label = "Conservative"

    # allocation percentages
    if label == "Aggressive":
        alloc = {"Equity Mutual Funds": 40, "Direct Stocks": 30, "Crypto": 15,
                 "Debt / Gold": 10, "Cash": 5}
    elif label == "Moderate":
        alloc = {"Equity Mutual Funds": 45, "Direct Stocks": 20, "Crypto": 8,
                 "Debt / Gold": 22, "Cash": 5}
    else:
        alloc = {"Equity Mutual Funds": 30, "Direct Stocks": 10, "Crypto": 0,
                 "Debt / Gold": 45, "Cash": 15}

    explanation = (f"Age {age} · {horizon_years}-yr horizon · {appetite} appetite → "
                   f"{label} profile (score {score}/100).")
    return {"score": score, "label": label, "allocation": alloc,
            "explanation": explanation}


def allocation_plan(amount, alloc, top_funds, top_stocks, top_crypto):
    """
    Splits `amount` and attaches concrete suggestions.
    top_funds: [{name, category, score}], top_stocks: [{name, signal, score}],
    top_crypto: [{name, signal, score}]
    Returns a list of buckets with suggestions.
    """
    plan = []
    for bucket, pct in alloc.items():
        amt = amount * pct / 100.0
        picks = []
        if bucket == "Equity Mutual Funds":
            picks = [f"{f['name'][:34]}" for f in (top_funds or [])[:3]]
        elif bucket == "Direct Stocks":
            picks = [f"{s['name'][:30]} ({s['signal']})" for s in (top_stocks or [])[:3]]
        elif bucket == "Crypto":
            picks = [f"{c['name'][:22]} ({c['signal']})" for c in (top_crypto or [])[:3]]
        elif bucket == "Debt / Gold":
            picks = ["Debt funds (HDFC Corporate Bond)", "Gold ETF / SGB"]
        elif bucket == "Cash":
            picks = ["Liquid funds / savings"]
        plan.append({
            "bucket": bucket, "pct": pct, "amount": round(amt, 2),
            "suggestions": picks,
        })
    return plan


def goal_plan(target, years, monthly=0.0, lumpsum=0.0, expected_return=12.0):
    """
    Returns:
      - required_monthly: SIP needed (if monthly not given) to reach target
      - projected: what the given monthly+lumpsum grows to
    """
    r = expected_return / 100.0
    rm = (1 + r) ** (1 / 12.0) - 1.0
    n = years * 12
    out = {"target": target, "years": years, "expected_return": expected_return}

    # future value of lumpsum
    lumpsum_fv = lumpsum * (1 + r) ** years

    if monthly and monthly > 0:
        fv_sip = monthly * ((1 + rm) ** n - 1) / rm * (1 + rm)
        total_fv = fv_sip + lumpsum_fv
        out["projected"] = round(total_fv, 2)
        out["invested"] = round(monthly * n + lumpsum, 2)
        out["shortfall"] = round(max(0.0, target - total_fv), 2)
        out["surplus"] = round(max(0.0, total_fv - target), 2)
    else:
        # required monthly to hit target after lumpsum
        need = max(0.0, target - lumpsum_fv)
        if need <= 0:
            out["required_monthly"] = 0.0
        elif rm > 0:
            out["required_monthly"] = round(need * rm / ((1 + rm) ** n - 1) / (1 + rm), 2)
        else:
            out["required_monthly"] = round(need / n, 2)
        out["lumpsum_now"] = round(lumpsum, 2)
        out["lumpsum_needed"] = round(target / ((1 + r) ** years), 2) if r > -1 else None
    return out


def suggest_horizon(years, top_funds):
    """Pick suitable fund categories by horizon."""
    if years <= 3:
        cats = ["Debt", "Hybrid"]
    elif years <= 5:
        cats = ["Hybrid", "Large Cap", "Index"]
    else:
        cats = ["Flexi Cap", "Mid Cap", "Small Cap", "Large Cap"]
    picks = [f for f in (top_funds or []) if f.get("category") in cats][:3]
    return cats, picks
