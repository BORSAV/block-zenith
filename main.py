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
    """ Scans NIFTY & BANKNIFTY option-chain for institutional activity """

    while True:
        if not session["token"]:
            print("[WAIT] Token not armed. sleeping 10s...")
            time.sleep(10)
            continue

        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[{datetime.now()}] scanning market...")

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

            try:
                r = requests.post(url, json=payload, headers=headers)
                raw_text = r.text  # keeps debug copy
                response = r.json()

            except Exception as ex:
                print(f"[X] Scan error {name}: {ex}")
                print("[DBG] raw response:", raw_text)
                continue

            # validate data
            if not response.get("data") or not response["data"].get("oc"):
                print(f"[!] No option-chain data returned for {name}")
                print("[DBG] full response:", response)
                continue

            # -------- scan each strike ----------
            for strike, chain in response["data"]["oc"].items():
                ce = chain.get("ce", {})
                pe = chain.get("pe", {})

                # both calls & puts, same logic
                for side, data in [("CE", ce), ("PE", pe)]:
                    volume = data.get("volume", 0)
                    oi = data.get("oi", 0)

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
                            f"🔥 _Detection: Smart Money Activity_"
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
        "Send your *Daily Dhan Access Token* to arm institutional scanner."
    )


@bot.message_handler(func=lambda msg: len(msg.text) > 100)
def arm(m):
    session["token"] = m.text.strip()
    bot.reply_to(
        m,
        "🚀 *System Armed.*\n"
        "Tracking Smart Money in NIFTY & BANKNIFTY.\n"
        "_Alerts will appear automatically._"
    )
    print("[+] New token armed — alerts reset")


# -----------------[ LAUNCH BOT + SERVER ]------------------------
if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
