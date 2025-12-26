import telebot
import os
import time
import requests
from datetime import datetime
import pytz
from flask import Flask
from threading import Thread

# === CONFIG ===
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
CHANNEL_ID = os.environ.get('CHANNEL_ID', '').strip()
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID', '').strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

# === IST MARKET TIMEZONE ===
IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)

def is_market_open():
    now = datetime.now(IST)
    h, m = now.hour, now.minute
    return (h > MARKET_OPEN[0] or (h == MARKET_OPEN[0] and m >= MARKET_OPEN[1])) and \
           (h < MARKET_CLOSE[0] or (h == MARKET_CLOSE[0] and m <= MARKET_CLOSE[1]))

# === BLOCK ZENITH SCANNER ===
def block_zenith_logic():
    while True:
        now = datetime.now(IST)
        print(f"[{now}] scanning market...")

        if not session["token"]:
            print("[WAIT] Token not armed. sleeping 10s...")
            time.sleep(10)
            continue

        if not is_market_open():
            print("[SLEEP] Market closed. Sleeping 5m...")
            time.sleep(300)
            continue

        today = datetime.now(IST).strftime('%Y-%m-%d')
        headers = {
            "access-token": session["token"],
            "client-id": MY_CLIENT_ID,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
            url = "https://api.dhan.co/v2/optionchain"
            payload = {
                "UnderlyingScrip": idx_id,
                "UnderlyingSeg": "IDX_I",
                "Expiry": today
            }

            try:
                r = requests.post(url, json=payload, headers=headers)
                if "html" in r.text.lower():
                    print(f"[SKIP] {name} returned non-JSON (502/closed).")
                    continue

                data = r.json().get("data", {}).get("oc", {})

                if not data:
                    print(f"[!] no option data for {name}", r.json())
                    continue

                for strike_price, strike in data.items():
                    for side_key, side_label in [("ce", "CE"), ("pe", "PE")]:
                        opt = strike.get(side_key)
                        if not opt:
                            continue

                        volume = opt.get("volume", 0)
                        oi = opt.get("oi", 0)
                        ltp = opt.get("last_price", 0)

                        # Your thresholds
                        if volume > 150000 or oi > 75000:
                            signal_type = "🏛️ INSTITUTIONAL CALL" if side_label == "CE" else "🏛️ INSTITUTIONAL PUT"
                            msg = (
                                f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                                f"Index: *{name}*\n"
                                f"Signal: *{signal_type}*\n"
                                f"Strike: *{strike_price}*\n"
                                f"Price: ₹{ltp}\n\n"
                                f"📊 *METRICS:*\n"
                                f"└ Volume: {volume:,}\n"
                                f"└ OI: {oi:,}\n\n"
                                f"🔥 _Smart Money Activity Detected_"
                            )
                            bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")

                time.sleep(2)

            except Exception as e:
                print(f"[X] Scan error {name}: {e}")
                continue

        print("[✓] scan OK — sleeping 60s...\n")
        time.sleep(60)

# === FLASK SERVER ===
app = Flask('')
@app.route('/')
def home(): return "Block Zenith Scanner Active"

# === TELEGRAM HANDLERS ===
@bot.message_handler(commands=["start"])
def welcome(m):
    bot.reply_to(m, "🏛️ Block Zenith is ready. Send your Dhan token.")

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm(m):
    session["token"] = m.text.strip()
    bot.reply_to(m, "🚀 System armed. Waiting for market & signals.")
    print("[+] New token armed.")

# === RUN ===
if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
