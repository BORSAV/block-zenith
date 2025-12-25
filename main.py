import telebot
import os
import time
import sqlite3
import requests
from datetime import datetime
from flask import Flask
from threading import Thread

# ==============================
# 1️⃣ ENVIRONMENT SETUP
# ==============================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
CHANNEL_ID = os.environ.get('CHANNEL_ID', '').strip()
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID', '').strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

# ==============================
# 2️⃣ ALERT STORAGE (avoid spam)
# ==============================
def init_db():
    conn = sqlite3.connect("alerts.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            strike INTEGER,
            side TEXT,
            price REAL,
            volume INTEGER,
            oi INTEGER,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def alert_exists(strike, side, volume, oi):
    conn = sqlite3.connect("alerts.db")
    c = conn.cursor()
    c.execute("""
        SELECT 1 FROM alerts
        WHERE strike=? AND side=? AND volume=? AND oi=?
    """, (strike, side, volume, oi))
    r = c.fetchone()
    conn.close()
    return r is not None

def store_alert(strike, side, volume, oi, price):
    conn = sqlite3.connect("alerts.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO alerts (strike, side, price, volume, oi)
        VALUES (?, ?, ?, ?, ?)
    """, (strike, side, price, volume, oi))
    conn.commit()
    conn.close()

# ==============================
# 3️⃣ BLOCK ZENITH SCANNER
# ==============================
def block_zenith_logic():
    print("[+] Scanner started — waiting for token...")

    while True:
        if not session['token']:
            print("[WAIT] Token not armed. sleeping 10s...")
            time.sleep(10)
            continue

        print(f"[{datetime.now()}] scanning...")

        today = datetime.now().strftime('%Y-%m-%d')
        url = "https://api.dhan.co/v2/optionchain"
        headers = {
            "access-token": session["token"],
            "client-id": MY_CLIENT_ID,
            "Content-Type": "application/json"
        }

        for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
            payload = {
                "UnderlyingScrip": idx_id,
                "UnderlyingSeg": "IDX_I",
                "Expiry": today
            }

            try:
                r = requests.post(url, json=payload, headers=headers).json()
            except Exception as e:
                print(f"[X] Scan error {name}: {e}")
                continue

            oc_data = r.get("data", {}).get("oc", {})
            if not oc_data:
                print(f"[!] No option data for {name}")
                continue

            for strike, data in oc_data.items():
                for side, opt in [("CE", data.get("ce")), ("PE", data.get("pe"))]:
                    if not opt:
                        continue

                    vol, oi, price = opt['volume'], opt['oi'], opt['last_price']

                    # --- institutional detection rules ---
                    if vol > 150000 or oi > 75000:
                        if alert_exists(strike, side, vol, oi):
                            continue

                        alert_type = "🏛️ INSTITUTIONAL CALL" if side == "CE" else "🏛️ INSTITUTIONAL PUT"
                        msg = (
                            f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                            f"Index: *{name}*\n"
                            f"Signal: *{alert_type}*\n"
                            f"Strike: *{strike}*\n"
                            f"Price: ₹{price}\n\n"
                            f"📊 *BLOCK METRICS:*\n"
                            f"└ Volume: {vol:,}\n"
                            f"└ Open Interest: {oi:,}\n\n"
                            f"🔥 _Detection: Smart Money Activity_"
                        )

                        try:
                            bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
                            print(f"[ALERT] {name} {strike} {side} sent")
                            store_alert(strike, side, vol, oi, price)
                        except Exception as e:
                            print(f"[X] Telegram error: {e}")

            time.sleep(2)

        print("[✓] cycle OK — sleeping 60s...")
        time.sleep(60)


# ==============================
# 4️⃣ FLASK SERVER (Railway)
# ==============================
app = Flask('')
@app.route('/')
def home():
    return "Block Zenith live 24/7"


# ==============================
# 5️⃣ TELEGRAM BOT
# ==============================
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m,
        "🏛️ *Block Zenith Terminal Ready.*\n\n"
        "Send your *Dhan Access Token* to arm system."
    )

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm(m):
    session["token"] = m.text.strip()
    bot.reply_to(m, "🚀 Token armed. Tracking Institutional Flow now.")
    conn = sqlite3.connect("alerts.db")
    conn.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()
    print("[+] New token armed — alerts reset")


# ==============================
# 6️⃣ STARTUP
# ==============================
if __name__ == "__main__":
    init_db()
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
