"""
report.py — generates the daily PDF report (reportlab).

Contents: market snapshot, top auto picks, mutual fund leaders,
market movers summary, your watchlist P&L, disclaimer.
"""
import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

FONT = "DejaVu"
FONT_B = "DejaVu-Bold"
_fonts_ok = False


def _init_fonts():
    global _fonts_ok
    if _fonts_ok:
        return
    try:
        pdfmetrics.registerFont(TTFont(FONT, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont(FONT_B, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        _fonts_ok = True
    except Exception:
        pass


GREEN = colors.HexColor("#16c784")
RED = colors.HexColor("#ea3943")
DARK = colors.HexColor("#131a27")
ACCENT = colors.HexColor("#3b82f6")
GREY = colors.HexColor("#8b98a5")
LIGHT = colors.HexColor("#f2f5f8")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("RTitle", fontName=FONT_B, fontSize=20, leading=24, textColor=colors.white))
    s.add(ParagraphStyle("RSub", fontName=FONT, fontSize=10, leading=13, textColor=colors.HexColor("#c8d4e0")))
    s.add(ParagraphStyle("RH2", fontName=FONT_B, fontSize=13, leading=16, textColor=DARK, spaceBefore=6))
    s.add(ParagraphStyle("RBody", fontName=FONT, fontSize=9, leading=12, textColor=colors.HexColor("#1c2b3a")))
    s.add(ParagraphStyle("RCell", fontName=FONT, fontSize=8, leading=10, textColor=colors.HexColor("#1c2b3a")))
    s.add(ParagraphStyle("RCellB", fontName=FONT_B, fontSize=8, leading=10, textColor=colors.HexColor("#1c2b3a")))
    s.add(ParagraphStyle("RCellC", parent=s["RCell"], alignment=TA_CENTER))
    s.add(ParagraphStyle("RCellR", parent=s["RCell"], alignment=TA_RIGHT))
    s.add(ParagraphStyle("RNote", fontName=FONT, fontSize=7.5, leading=10, textColor=GREY))
    return s


def _money(x, cur):
    if x is None:
        return "—"
    sign = "−" if x < 0 else ""
    ax = abs(x)
    if cur == "INR":
        return f"{sign}₹{ax:,.0f}"
    return f"{sign}${ax:,.2f}"


def _pct(x, signed=True):
    if x is None:
        return "—"
    return f"{'+' if signed and x > 0 else ''}{x:.2f}%"


def _p(*args):
    return Paragraph(*args)


def _build(styles, signals, funds, movers, watchlist):
    S = styles
    story = []
    today = datetime.now().strftime("%d %B %Y")

    # ---- header band ----
    head = Table([[
        _p("Daily Stock, Crypto & Mutual Fund Analysis", S["RTitle"]),
    ]], colWidths=[180 * mm])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    sub = Table([[
        _p(f"Report date: <b>{today}</b>  ·  Generated {datetime.now().strftime('%H:%M')} IST  ·  "
           f"Data: CoinGecko / Yahoo Finance / AMFI (free, delayed)", S["RSub"]),
    ]], colWidths=[180 * mm])
    sub.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#223044")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story += [head, sub, Spacer(1, 6)]

    # ---- 1. top auto picks ----
    story.append(_p("1 · Top Auto Picks Today (scanned & ranked)", S["RH2"]))
    rows = [[_p("Rank", S["RCellB"]), _p("Asset", S["RCellB"]), _p("Market", S["RCellB"]),
             _p("Signal", S["RCellB"]), _p("Price", S["RCellB"]), _p("Target", S["RCellB"]),
             _p("Stop", S["RCellB"]), _p("Gain @target", S["RCellB"]), _p("Loss @stop", S["RCellB"]),
             _p("Hold", S["RCellB"])]]
    all_items = []
    for key, label in (("stocks_in", "India"), ("crypto", "Crypto"), ("stocks_us", "US")):
        for it in (signals or {}).get(key, []):
            if it["signal"] in ("STRONG BUY", "BUY"):
                all_items.append((it, label))
    all_items.sort(key=lambda x: -x[0]["score"])
    for rank, (it, mkt) in enumerate(all_items[:10], 1):
        rows.append([
            _p(str(rank), S["RCellC"]),
            _p(f"<b>{it['name']}</b>", S["RCell"]),
            _p(mkt, S["RCell"]),
            _p(f"<font color='#16c784'><b>{it['signal']}</b></font>", S["RCell"]),
            _p(_money(it["price"], it["currency"]), S["RCellR"]),
            _p(_money(it["target"], it["currency"]), S["RCellR"]),
            _p(_money(it["stop"], it["currency"]), S["RCellR"]),
            _p(f"<font color='#16c784'>+{_pct(it['pnl_pct_target'], False)}</font>", S["RCellR"]),
            _p(f"<font color='#ea3943'>{_pct(it['pnl_pct_stop'], False)}</font>", S["RCellR"]),
            _p(it["hold_label"].replace(" trading days", "d"), S["RCell"]),
        ])
    t = Table(rows, colWidths=[10 * mm, 40 * mm, 16 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 26 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story += [t, Spacer(1, 8)]

    # ---- 2. mutual funds ----
    if funds and funds.get("funds"):
        story.append(_p("2 · Mutual Fund Leaders (1-year & 3-year performance)", S["RH2"]))
        frows = [[_p("Fund", S["RCellB"]), _p("Cat", S["RCellB"]), _p("NAV", S["RCellB"]),
                  _p("1M", S["RCellB"]), _p("1Y", S["RCellB"]), _p("3Y", S["RCellB"]),
                  _p("5Y", S["RCellB"]), _p("Risk", S["RCellB"]), _p("Rating", S["RCellB"])]]
        for f in funds["top"][:8]:
            frows.append([
                _p(f"<b>{f['name']}</b>", S["RCell"]),
                _p(f["category"], S["RCell"]),
                _p(f"₹{f['nav']:.2f}", S["RCellR"]),
                _p(_pct(f["r1m"], False), S["RCellR"]),
                _p(_pct(f["r1y"], False), S["RCellR"]),
                _p(_pct(f["r3y"], False), S["RCellR"]),
                _p(_pct(f["r5y"], False), S["RCellR"]),
                _p("High" if (f["volatility"] or 0) >= 18 else "Med" if (f["volatility"] or 0) >= 10 else "Low", S["RCellR"]),
                _p(f"<b>{f['rating']}</b> ({(f['score']):.0f})", S["RCell"]),
            ])
        ft = Table(frows, colWidths=[72 * mm, 18 * mm, 20 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm, 26 * mm], repeatRows=1)
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ec")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story += [ft, Spacer(1, 8)]

    # ---- 3. market movers ----
    if movers:
        story.append(_p("3 · Market Movers (24h)", S["RH2"]))
        mrows = [[_p("Market", S["RCellB"]), _p("Top Gainer", S["RCellB"]), _p("Top Loser", S["RCellB"])]]
        for key, label in (("stocks_in", "Indian Stocks"), ("crypto", "Crypto"), ("stocks_us", "US Stocks")):
            seg = movers.get(key) or {}
            g = (seg.get("gainers") or [None])[0]
            l = (seg.get("losers") or [None])[0]
            mrows.append([
                _p(f"<b>{label}</b>", S["RCell"]),
                _p(f"{g['name']}  <font color='#16c784'>+{_pct(g['change_pct'], False)}</font>" if g else "—", S["RCell"]),
                _p(f"{l['name']}  <font color='#ea3943'>{_pct(l['change_pct'], False)}</font>" if l else "—", S["RCell"]),
            ])
        mt = Table(mrows, colWidths=[32 * mm, 76 * mm, 76 * mm], repeatRows=1)
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ec")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [mt, Spacer(1, 8)]

    # ---- 4. your picks ----
    items = (watchlist or {}).get("items") or []
    if items:
        story.append(_p("4 · Your Picks — Live Profit / Loss", S["RH2"]))
        prows = [[_p("Asset", S["RCellB"]), _p("Buy", S["RCellB"]), _p("Qty", S["RCellB"]),
                  _p("Now", S["RCellB"]), _p("Invested", S["RCellB"]), _p("Value", S["RCellB"]),
                  _p("P&L", S["RCellB"]), _p("P&L %", S["RCellB"])]]
        for it in items:
            col = "#16c784" if (it["pnl"] or 0) >= 0 else "#ea3943"
            prows.append([
                _p(f"<b>{it['name']}</b>", S["RCell"]),
                _p(_money(it["buy_price"], it["currency"]), S["RCellR"]),
                _p(f"{it['qty']:g}", S["RCellR"]),
                _p(_money(it["current_price"], it["currency"]), S["RCellR"]),
                _p(_money(it["invested"], it["currency"]), S["RCellR"]),
                _p(_money(it["value"], it["currency"]), S["RCellR"]),
                _p(f"<font color='{col}'><b>{_money(it['pnl'], it['currency'])}</b></font>", S["RCellR"]),
                _p(f"<font color='{col}'>{_pct(it['pnl_pct'])}</font>", S["RCellR"]),
            ])
        pt = Table(prows, colWidths=[44 * mm, 22 * mm, 14 * mm, 22 * mm, 22 * mm, 22 * mm, 24 * mm, 18 * mm], repeatRows=1)
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ec")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story += [pt, Spacer(1, 8)]

    story += [Spacer(1, 6), HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#dbe4ec")), Spacer(1, 4),
              _p("Disclaimer: This report is auto-generated for educational purposes only and is <b>not investment advice</b>. "
                 "Signals and projections are statistical estimates based on free, delayed data (stocks ~15 min; mutual-fund NAVs update after market close). "
                 "Markets can move against any signal — always use a stop-loss and invest only what you can afford to lose.",
                 S["RNote"])]
    return story


def generate_pdf(signals=None, funds=None, movers=None, watchlist=None):
    """Builds the PDF and returns (path, filename)."""
    _init_fonts()
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title="Daily Market Analysis",
                            author="Daily Market Analyzer")
    story = _build(styles, signals, funds, movers, watchlist)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(14 * mm, 8 * mm, "Daily Market Analyzer — free data (CoinGecko · Yahoo Finance · AMFI)")
        canvas.drawRightString(196 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    fname = f"daily_analysis_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    path = os.path.join(REPORTS_DIR, fname)
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return path, fname
