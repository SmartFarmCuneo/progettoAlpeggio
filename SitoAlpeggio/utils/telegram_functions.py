import threading
from datetime import datetime
import requests
import time
from utils.db_connection import get_db_connection

BOT_TOKEN = ""


def get_telegram_chat_id(username):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT telegram_chat_id FROM users WHERE username = %s", (username,))
        info = cursor.fetchone()
    return info

def send_telegram_notification(title, message, chat_id): # mettere il chat id
    print("Invio notifica Telegram...")
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": chat_id['telegram_chat_id'], "text": message},
        timeout=5
    )
    print("Risposta Telegram:", r.status_code, r.text)

def set_bot_commands():
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands",
            json={"commands": [{"command": "start","description": "Avvia il bot"},
                {"command": "stop","description": "Ferma irrigazione"}]},timeout=5)
    except Exception as e:
        print("[TELEGRAM] errore setMyCommands:", e)

def telegram_listener(chat_id):
    offset = None
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset},
                timeout=10
            )
            updates = r.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                if "message" in u:
                    msg = u["message"]
                    text = msg.get("text", "")
                    chat_id = msg["chat"]["id"]
                    if chat_id != chat_id:
                        continue

                    if text == "/start":
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "Bot attivo ✔"
                            },
                            timeout=5
                        )

                    elif text == "/stop":
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "🛑 Irrigazione fermata"
                            },
                            timeout=5
                        )

        except Exception as e:
            print("[TELEGRAM] errore:", e)

        time.sleep(2)