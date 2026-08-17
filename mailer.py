"""
mailer.py — SMTP email sending for price alerts (configurable).

Settings live in data/settings.json. Works with Gmail (use an App Password),
or any SMTP provider. The user enters their own credentials in the ⚙ Settings
panel — nothing is hard-coded here.
"""
import os
import json
import smtplib
import threading
from email.mime.text import MIMEText

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

DEFAULTS = {
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "from_addr": "",
    "to_addr": "",
    # daily advisory email
    "daily_email_enabled": False,
    "daily_email_time": "08:00",
    # Telegram bot (free phone alerts + advisor chat)
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_daily_enabled": False,
    # free API keys (optional)
    "twelve_data_key": "",
    "finnhub_key": "",
    "alpha_vantage_key": "",
    # Zerodha Kite (optional, true real-time NSE)
    "zerodha_enabled": False,
    "zerodha_api_key": "",
    "zerodha_api_secret": "",
    "zerodha_access_token": "",
    # Angel One SmartAPI (optional, FREE real-time NSE for Angel One customers)
    "angel_enabled": False,
    "angel_api_key": "",
    "angel_client_code": "",
    "angel_password": "",
    "angel_totp": "",
    # Google Finance fallback (free, no key) — used when Yahoo is blocked
    "google_finance_enabled": True,
}

_lock = threading.Lock()


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
        return {**DEFAULTS, **s}
    except Exception:
        return dict(DEFAULTS)


def save_settings(s):
    with _lock:
        out = {k: s.get(k, v) for k, v in DEFAULTS.items()}
        out["smtp_port"] = int(out["smtp_port"] or 587)
        out["email_enabled"] = bool(out.get("email_enabled"))
        with open(SETTINGS_FILE, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def public_settings():
    """Settings safe to show in the UI (mask secrets)."""
    s = load_settings()
    s["smtp_pass_set"] = bool(s.get("smtp_pass"))
    s["smtp_pass"] = ""
    for k in ("zerodha_access_token", "zerodha_api_secret", "angel_password", "angel_totp"):
        if s.get(k):
            s[k + "_set"] = True
            s[k] = ""
        else:
            s[k + "_set"] = False
    return s


def send_email(subject, body):
    """Send an email using the saved SMTP settings. Returns (ok, message)."""
    s = load_settings()
    if not s.get("email_enabled"):
        return False, "Email alerts are disabled"
    if not s.get("to_addr") or not s.get("smtp_user"):
        return False, "Email not configured (missing To address or SMTP user)"
    if not s.get("smtp_pass"):
        return False, "SMTP password not set"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = s.get("from_addr") or s.get("smtp_user")
    msg["To"] = s.get("to_addr")

    try:
        port = int(s.get("smtp_port") or 587)
        with smtplib.SMTP(s.get("smtp_host"), port, timeout=20) as server:
            server.ehlo()
            if port in (587, 465, 25):
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPNotSupportedError:
                    pass
            server.login(s.get("smtp_user"), s.get("smtp_pass"))
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
        return True, "Sent"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP login failed — check username/app-password"
    except Exception as e:
        return False, str(e)[:160]
