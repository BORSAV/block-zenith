import telebot
import os
import time
from datetime import datetime
from dhanhq import dhanhq
from flask import Flask
from threading import Thread

# --- 1. SECURE SETUP ---
# .strip() handles hidden characters from copy-pasting into Railway
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
CHANNEL_ID = os.environ.get('CHANNEL_ID', '').strip()
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID', '').strip()

bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

# --- 2. INSTITUTIONAL SCANNER ---
def block_zenith_logic():
    """Identifies where 'Big Money' is entering the market."""
    while True:
        if session["token"]:
            dhan = dhanhq(MY_CLIENT_ID, session["token"])
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Monitoring major indices
            for idx_id, name in [(13, "NIFTY"), (25, "BANKNIFTY")]:
                try:
                    response = dhan.get_option_chain(idx_id, "IDX_I", today)
                    if response.get('status') == 'success':
                        for oc in response['data']['oc']:
                            # Alert if strike has Volume > 1.5L or OI > 75k (High-Conviction Blocks)
                            for side, data in [("CE", oc['ce']), ("PE", oc['pe'])]:
                                if data['volume'] > 150000 or data['oi'] > 75000:
                                    alert_type = "🏛️ INSTITUTIONAL CALL" if side == "CE" else "🏛️ INSTITUTIONAL PUT"
                                    msg = (
                                        f"⚔️ *BLOCK ZENITH ORDER FLOW* ⚔️\n\n"
                                        f"Index: *{name}*\n"
                                        f"Signal: *{alert_type}*\n"
                                        f"Strike: *{oc['strike_price']}*\n"
                                        f"Price: ₹{data['last_price']}\n\n"
                                        f"📊 *BLOCK METRICS:*\n"
                                        f"└ Volume: {data['volume']:,}\n"
                                        f"└ Open Interest: {data['oi']:,}\n\n"
                                        f"🔥 _Detection: Smart Money Activity_"
                                    )
                                    bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
                    time.sleep(2)
                except Exception: continue
        time.sleep(300) # Re-scan every 5 minutes

# --- 3. RAILWAY SERVER & STARTUP ---
app = Flask('')
@app.route('/')
def home(): return "Block Zenith 24/7 Deployment Active"

@bot.message_handler(commands=['start'])
def welcome(m):
    bot.reply_to(m, "🏛️ *Block Zenith Terminal Ready.*\n\nPlease send your Daily Dhan Access Token to arm the scanner.")

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm(m):
    session["token"] = m.text
    bot.reply_to(m, "🚀 *System Armed.* Now tracking Institutional Flow in Nifty and BankNifty.")

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()
    Thread(target=block_zenith_logic).start()
    bot.infinity_polling()
