import telebot
import os
import time
from datetime import datetime
import pytz
from dhanhq import dhanhq
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
CHANNEL_ID = os.environ.get('CHANNEL_ID', '').strip()
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID', '').strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

# --- MARKET TIME SETTINGS (IST) ---
IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN = (9, 15)     # 9:15 AM IST
MARKET_CLOSE = (15, 30)   # 3:30 PM IST


def is_market_open():
    """Check NSE market hours using Indian time."""
    now = datetime.now(IST)
    h, m = now.hour, now.minute
    return (h > MARKET_OPEN[0] or (h == MARKET_OPEN[0] and m >= MARKET_OPEN[1])) and \
           (h < MARKET_CLOSE[0] or (h == MARKET_CLOSE[0] and m <= MARKET_CLOSE[1]))


# --- INSTITUTIONAL SCANNER ---
def block_zenith_logic():
    while True:
        now = datetime.now(IST)
        print(f"[{now}] scanning market...")

        if not session["token"]:
            print("[WAIT] Token not armed. sleeping 10s...")
            time.sleep(10)
            continue

        # Check market status
        if not is_market_open():
            print("[SLEEP] Market closed. Sleeping 5m...")
            time.sleep(300)
            continue

        dhan = dhanhq(MY_CLIENT_ID, session["token"])

        for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
            try:
                oc_data = dhan.instruments.option_chain(idx_id, "INDEX")
                data = oc_data.get("data", [])

                for strike in data:
                    for side in ["CE", "PE"]:
                        opt = strike.get(side, {})
                        if not opt:
                            continue

                        volume = opt.get("volume", 0)
                        oi = opt.get("open_interest", 0)

                        # Thresholds — adjust as you like
                        if volume > 150000 or oi > 75000:
                            alert_type = "🏛️ INSTITUTIONAL CALL" if side == "CE" else "🏛️ INSTITUTIONAL PUT"

                            msg = (
                                f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                                f"Index: *{name}*\n"
                                f"Signal: *{alert_type}*\n"
                                f"Strike: *{strike['strike_price']}*\n"
                                f"Price: ₹{opt.get('last_traded_price','-')}\n\n"
                                f"📊 *BLOCK METRICS:*\n"
                                f"└ Volume: {volume:,}\n"
                                f"└ Open Interest: {oi:,}\n\n"
                                f"🔥 _Detection: Smart Money Activity_"
                            )
                            bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")

                time.sleep(2)
            except Exception as e:
                print(f"[X] Scan error {name}: {e}")
                continue

        print("[✓] scan OK — sleeping 60s...")
        time.sleep(60)


# --- FLASK SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Block Zenith 24/7 Deployment Active (IST Time Synced)"


# --- TELEGRAM HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m, "🏛️ *Block Zenith Ready.*\n\nSend today's Dhan Access Token to arm the scanner.")

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm(m):
    session["token"] = m.text
    bot.reply_to(m, "🚀 *System Armed.* Tracking institutional flow.\nWait for alerts when market opens.")
    print("[+] New token armed — alerts reset")


# --- STARTUP ---
if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
