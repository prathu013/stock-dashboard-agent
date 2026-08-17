"""
portfolio.py — portfolio health (concentration, volatility, diversification)
and Indian capital-gains tax estimate (FY 2026-27 rules).

Tax rules used (Budget 2026 kept rates unchanged):
  - Listed equity (Indian stocks, equity MFs): STCG <=12mo = 20%; LTCG >12mo =
    12.5% above Rs 1.25L annual exemption.
  - Crypto/VDA: 30% flat, no set-off, no exemption.
  - Foreign equity (US stocks): <24mo = slab (assumed, default 30% top slab);
    >=24mo = 12.5% LTCG.

These are estimates for planning — consult a CA for actual filing.
"""
from datetime import datetime, timezone

RISK_FREE = 6.5  # %


def holding_days(added_at):
    if not added_at:
        return None
    try:
        added = datetime.fromisoformat(added_at)
    except Exception:
        return None
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - added).days


def health(watch_items, vols_by_id):
    """
    watch_items: list of dicts (id, name, currency, invested, value, pnl, type)
    vols_by_id: {item_id: annualized_vol_percent}
    Returns concentration, diversification and weighted risk.
    """
    if not watch_items:
        return None
    total = sum((i.get("value") or i.get("invested") or 0) for i in watch_items)
    if total <= 0:
        return None

    # concentration
    shares = [(i["name"], (i.get("value") or 0) / total) for i in watch_items]
    shares.sort(key=lambda x: -x[1])
    top = shares[0]
    hhi = sum(s * s for _, s in shares) * 10000
    n = len(shares)
    divers = max(0.0, min(100.0, 100 - hhi / 100.0))
    if divers >= 70:
        divers_label = "Well diversified"
    elif divers >= 45:
        divers_label = "Moderately diversified"
    else:
        divers_label = "Concentrated"

    # weighted volatility
    wvol = 0.0
    known = 0
    for i in watch_items:
        v = vols_by_id.get(i.get("id"))
        if v is not None:
            wvol += (v or 0) * ((i.get("value") or 0) / total)
            known += 1
    wvol = round(wvol, 2)
    if wvol >= 25:
        risk_label = "High risk"
    elif wvol >= 12:
        risk_label = "Medium risk"
    else:
        risk_label = "Low risk"

    advice = []
    if top[1] > 0.5:
        advice.append(f"{top[0]} is {round(top[1]*100)}% of your portfolio — consider reducing concentration.")
    if n < 5 and total > 0:
        advice.append(f"You hold only {n} asset(s); spreading across sectors lowers risk.")
    if wvol >= 25:
        advice.append("Portfolio volatility is high — consider adding less volatile assets (debt, large-caps, index).")

    return {
        "total": round(total, 2),
        "n_assets": n,
        "top": {"name": top[0], "share": round(top[1] * 100, 1)},
        "hhi": round(hhi, 0),
        "diversification": round(divers, 1),
        "divers_label": divers_label,
        "weighted_vol": wvol,
        "risk_label": risk_label,
        "advice": advice[:4],
    }


def tax_estimate(items, slab_rate=30.0):
    """
    items: list with {type, currency, pnl, invested, value, added_at}
    Returns per-asset tax + totals. Only realized-ish gains counted (unrealized
    gains on holdings are treated as "if sold today").
    """
    rows = []
    equity_ltcg_total = 0.0
    equity_stcg_total = 0.0
    crypto_tax = 0.0
    foreign_tax = 0.0

    for it in items:
        pnl = it.get("pnl") or 0
        if pnl <= 0:
            continue
        days = holding_days(it.get("added_at"))
        typ = it.get("type")
        cur = it.get("currency") or "INR"
        tax = None
        note = ""

        if typ == "crypto":
            tax = pnl * 0.30
            crypto_tax += tax
            note = "30% flat (crypto/VDA)"
        elif typ == "stock_in" or cur == "INR":
            if days is not None and days > 365:
                equity_ltcg_total += pnl
                note = f"LTCG 12.5% (>1yr held)"
            else:
                equity_stcg_total += pnl
                note = f"STCG 20% (held {days if days is not None else '?'}d)"
        elif cur == "USD":  # foreign equity
            if days is not None and days > 730:
                tax = pnl * 0.125
                foreign_tax += tax
                note = "Foreign LTCG 12.5% (>2yr)"
            else:
                tax = pnl * slab_rate / 100.0
                foreign_tax += tax
                note = f"Foreign STCG @slab {slab_rate}%"
        rows.append({
            "name": it.get("name"), "pnl": round(pnl, 2), "currency": cur,
            "days": days, "tax": round(tax, 2) if tax is not None else None,
            "note": note,
        })

    exemption = 125000.0
    taxable_ltcg = max(0.0, equity_ltcg_total - exemption)
    equity_ltcg_tax = taxable_ltcg * 0.125
    equity_stcg_tax = equity_stcg_total * 0.20

    totals = {
        "equity_ltcg": round(equity_ltcg_total, 2),
        "equity_stcg": round(equity_stcg_total, 2),
        "equity_ltcg_tax": round(equity_ltcg_tax, 2),
        "equity_stcg_tax": round(equity_stcg_tax, 2),
        "crypto_tax": round(crypto_tax, 2),
        "foreign_tax": round(foreign_tax, 2),
        "grand_total": round(equity_ltcg_tax + equity_stcg_tax + crypto_tax + foreign_tax, 2),
        "ltcg_exemption_used": round(min(equity_ltcg_total, exemption), 2),
        "slab_rate": slab_rate,
    }
    return {"rows": rows, "totals": totals}
