"""
telegram_bot.py — free Telegram integration.

Once the user pastes a bot token (from @BotFather) and their chat id in
⚙ Settings, this module:
  - sends price alerts & the daily advisory to their phone via Telegram
  - runs a long-poll loop so they can CHAT with the advisor from Telegram
    (commands: /help /market /best /funds /portfolio /ask ... /price SYMBOL)

No extra dependencies (uses `requests`, already installed).
"""
import time

import requests

BASE = "https://api.telegram.org/bot{token}/{method}"
UA = {"User-Agent": "Mozilla/5.0"}


def configured(settings):
    return bool(settings.get("telegram_bot_token") and settings.get("telegram_chat_id"))


def _call(token, method, **params):
    try:
        r = requests.post(BASE.format(token=token, method=method),
                          data=params, timeout=25, headers=UA)
        return r.json()
    except Exception:
        return {"ok": False, "error": "network error"}


def send_message(text, settings=None, token=None, chat_id=None):
    if settings:
        token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
    if not token or not chat_id:
        return False, "Telegram not configured (need bot token + chat id)"
    if len(text) > 4000:
        text = text[:3950] + "…"
    j = _call(token, "sendMessage", chat_id=chat_id, text=text)
    if j.get("ok"):
        return True, "Sent"
    return False, j.get("description") or "Telegram error"


def discover_chat_id(token):
    """Read recent messages to find the user's chat id (they must have
    messaged the bot first)."""
    if not token:
        return None
    j = _call(token, "getUpdates", limit=5, timeout=0)
    ids = []
    for u in j.get("result", []):
        m = u.get("message") or u.get("edited_message")
        if m and m.get("chat"):
            ids.append(m["chat"]["id"])
    return ids[-1] if ids else None


def poll(handler, settings_provider, stop_event=None):
    """
    Long-poll getUpdates and hand each message to handler(text) -> reply str.
    handler is provided by app.py (has access to data engines).
    """
    offset = 0
    while not (stop_event and stop_event.is_set()):
        token = (settings_provider() or {}).get("telegram_bot_token")
        if not token:
            time.sleep(10)
            continue
        try:
            j = _call(token, "getUpdates", offset=offset, timeout=30)
            if j.get("ok"):
                for u in j.get("result", []):
                    offset = max(offset, u["update_id"] + 1)
                    m = u.get("message")
                    if not m or not m.get("text"):
                        continue
                    text = m["text"].strip()
                    chat = m["chat"]["id"]
                    try:
                        reply = handler(text)
                    except Exception as e:
                        reply = f"⚠️ Error: {e}"
                    if reply:
                        send_message(reply, token=token, chat_id=chat)
        except Exception:
            pass
        time.sleep(1)
