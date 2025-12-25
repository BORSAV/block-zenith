import os
import time
import requests
from datetime import datetime
from flask import Flask
from threading import Thread
import telebot

# -----------------[ ENV SETUP ]------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
MY_CLIENT_ID = os.environ.get("MY_CLIENT_ID", "").strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}


# -----------------[ SMART MONEY SCANNER ]------------------------
def block_zenith_logic():
    """Scans NIFTY & BANKNIFTY option-chain for institutional activity in live market"""

    while True:
        # -------- token check --------
        if not session["token"]:
            print("[WAIT] Token not armed. sleeping 10s...")
            time.sleep(10)
            continue

        # -------- optional market hours filter --------
        # market hours 9:15 to 15:30 — adjust if needed
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        if (hour < 9) or (hour == 9 and minute < 15) or (hour > 15 or (hour == 15 and minute > 30)):
            print("[SLEEP] Market closed. Sleeping 5m...")
            time.sleep(300)
            continue

        today = now.strftime("%Y-%m-%d")
        print(f"[{now}] scanning market...")

        # -------- index list --------
        for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
            url = "https://api.dhan.co/v2/optionchain"
            headers = {
                "access-token": session["token"],
                "client-id": MY_CLIENT_ID,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "UnderlyingScrip": idx_id,
                "UnderlyingSeg": "IDX_I",
                "Expiry": today
            }

            # -------- API call --------
            try:
                r = requests.post(url, json=payload, headers=headers)
                raw_text = r.text

                # --- fix: HTML or gateway errors ---
                if r.headers.get("Content-Type", "").startswith("text/html"):
                    print(f"[SKIP] {name} returned HTML (502 / market closed / gateway)")
                    continue

                if r.status_code >= 500:
                    print(f"[SKIP] {name} server error {r.status_code}")
                    continue

                response = r.json()

            except Exception as ex:
                print(f"[X] scan error {name}: {ex}")
                print("[DBG] raw response:", raw_text)
                continue

            # -------- data validation --------
            if not response.get("data") or not response["data"].get("oc"):
                print(f"[SKIP] No usable option-chain data for {name}")
                print("[DBG] full response:", response)
                continue

            # -------- scan each strike --------
            for strike, chain in response["data"]["oc"].items():
                ce = chain.get("ce", {})
                pe = chain.get("pe", {})

                for side, data in [("CE", ce), ("PE", pe)]:
                    volume = data.get("volume", 0)
                    oi = data.get("oi", 0)

                    # high conviction filters
                    if volume > 150000 or oi > 75000:
                        alert_type = "🏛️ INSTITUTIONAL CALL" if side == "CE" else "🏛️ INSTITUTIONAL PUT"
                        msg = (
                            f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                            f"Index: *{name}*\n"
                            f"Signal: *{alert_type}*\n"
                            f"Strike: *{strike}*\n"
                            f"Price: ₹{data.get('last_price', 0)}\n\n"
                            f"📊 *BLOCK METRICS:*\n"
                            f"└ Volume: {volume:,}\n"
                            f"└ Open Interest: {oi:,}\n\n"
                            f"🔥 _Detection: Fresh Smart Money_"
                        )
                        try:
                            bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
                            print(f"[ALERT] {name} {side} strike {strike}")
                        except Exception as e:
                            print("[X] Telegram send failed:", e)

        print("[✓] cycle OK — sleeping 60s...\n")
        time.sleep(60)


# -----------------[ TELEGRAM COMMANDS ]------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Block Zenith Scanner Active — Running 24/7"


@bot.message_handler(commands=["start"])
def welcome(m):
    bot.reply_to(
        m,
        "🏛️ *Block Zenith Terminal Online*\n\n"
        "Send your *Daily Dhan Access Token* to arm scanner.\n"
        "_Alerts only during market hours._"
    )


@bot.message_handler(func=lambda msg: len(msg.text) > 100)
def arm(m):
    session["token"] = m.text.strip()
    bot.reply_to(
        m,
        "🚀 *System Armed.* Tracking institutional flow.\n"
        "Wait for alerts when market opens."
    )
    print("[+] New token armed — alerts reset")


# -----------------[ LAUNCH ]------------------------
if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
