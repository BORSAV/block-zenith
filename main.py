import telebot
import os
import time
import json
from datetime import datetime
from dhanhq import dhanhq
from flask import Flask
from threading import Thread

# --- ENV SETUP ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
CHANNEL_ID = os.environ.get('CHANNEL_ID', '').strip()
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID', '').strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

# --- persistent storage for past alerts (survives restarts) ---
ALERT_DB = "alerts.db"
LAST_DATA = {}  # stores last volume/OI to detect jumps

def load_alerts():
    try:
        with open(ALERT_DB, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_alerts(alerts):
    with open(ALERT_DB, "w") as f:
        json.dump(list(alerts), f)

sent_alerts = load_alerts()


# --- SMART MONEY DETECTION ENGINE (1–4) ---
def block_zenith_logic():
    print("[+] Scanner started\n")

    while True:
        if not session["token"]:
            print("[WAIT] Token not armed. sleeping 10s...\n")
            time.sleep(10)
            continue

        dhan = dhanhq(MY_CLIENT_ID, session["token"])
        today = datetime.now().strftime('%Y-%m-%d')

        for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
            try:
                print(f"[{datetime.now()}] checking {name} ...")
                response = dhan.get_option_chain(idx_id, "IDX_I", today)

                # --- 1️⃣ Token expiry detection
                if response.get("status") == "error":
                    bot.send_message(CHANNEL_ID,
                        "⚠️ *Dhan Token Expired*\n\n"
                        "Please send fresh token to continue scanning.",
                        parse_mode="Markdown"
                    )
                    print("[!] TOKEN EXPIRED — waiting for new token")
                    session["token"] = None
                    break

                if response.get('status') != 'success':
                    print(f"[ERROR] Failed getting OC for {name}")
                    continue

                for oc in response['data']['oc']:
                    for side, data in [("CE", oc['ce']), ("PE", oc['pe'])]:
                        strike = oc['strike_price']
                        volume, oi = data['volume'], data['oi']
                        price = data['last_price']

                        key = f"{name}-{strike}-{side}"
                        prev_volume = LAST_DATA.get(key, {}).get("vol", 0)
                        prev_oi = LAST_DATA.get(key, {}).get("oi", 0)

                        # --- 2️⃣ Momentum jump detection
                        vol_jump = volume - prev_volume
                        oi_jump = oi - prev_oi

                        # --- 4️⃣ Smart money logic
                        good_level = volume > 150000 or oi > 75000
                        fresh_jump = vol_jump > 20000 or oi_jump > 10000  # live entry

                        if good_level and fresh_jump:
                            if key not in sent_alerts:
                                sent_alerts.add(key)
                                save_alerts(sent_alerts)

                                alert_type = "🏛️ INSTITUTIONAL CALL" if side == "CE" \
                                             else "🏛️ INSTITUTIONAL PUT"

                                msg = (
                                    f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                                    f"Index: *{name}*\n"
                                    f"Signal: *{alert_type}*\n"
                                    f"Strike: *{strike}*\n"
                                    f"Price: ₹{price}\n\n"
                                    f"📊 *BLOCK METRICS:*\n"
                                    f"└ Volume: {volume:,} (+{vol_jump:,})\n"
                                    f"└ Open Interest: {oi:,} (+{oi_jump:,})\n\n"
                                    f"🔥 _Fresh Smart Money Detected_"
                                )

                                print(f"[+] ALERT → {name} {side} {strike} (V+{vol_jump} / OI+{oi_jump})")
                                bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
                                time.sleep(1)

                        # update memory for next scan
                        LAST_DATA[key] = {"vol": volume, "oi": oi}

                time.sleep(2)

            except Exception as e:
                print(f"[X] Scan error {name}: {e}")
                continue

        print("[✓] cycle OK — sleeping 60s...\n")
        time.sleep(60)


# --- FLASK SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Block Zenith 24/7 Active"


# --- TELEGRAM COMMANDS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m,
        "🏛️ *Block Zenith Terminal Ready.*\n"
        "Send your Daily Dhan token to activate detection.",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm(m):
    session["token"] = m.text.strip()
    sent_alerts.clear()
    save_alerts(sent_alerts)
    bot.reply_to(m,
        "🚀 *System Armed.*\nTracking Fresh Institutional Flow...",
        parse_mode="Markdown"
    )
    print("[+] New token armed — alerts reset.")


# --- RUN ---
if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()
    Thread(target=block_zenith_logic, daemon=True).start()
    bot.infinity_polling()
