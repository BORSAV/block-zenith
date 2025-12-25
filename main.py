import telebot
import time
import os
from datetime import datetime
from dhanhq import dhanhq
from flask import Flask
from threading import Thread

# --- 1. SETUP ---
MY_CLIENT_ID = os.environ.get('MY_CLIENT_ID')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

INDICES = [{"name": "NIFTY", "id": 13}, {"name": "BANKNIFTY", "id": 25}]

# --- 2. THE ENGINE ---
bot = telebot.TeleBot(BOT_TOKEN)
session = {"token": None}

def send_block_alert(index, strike, opt_type, price, oi, vol):
    """Sends a specialized Institutional Flow alert."""
    icon = "🐋 WHALE BUY: CALL" if opt_type == "CE" else "🐋 WHALE BUY: PUT"
    msg = (
        f"🏛️ *BLOCK ZENITH INSIGHT* 🏛️\n\n"
        f"Index: *{index}*\n"
        f"Action: *{icon}*\n"
        f"Strike: *{strike}*\n"
        f"Entry Price: ₹{price}\n\n"
        f"📊 *INSTITUTIONAL DATA:*\n"
        f"└ Open Interest: {oi:,}\n"
        f"└ Day Volume: {vol:,}\n\n"
        f"🔥 _Smart Money is entering this strike!_"
    )
    bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")

def block_zenith_scanner():
    """Scans for high-volume institutional blocks."""
    while True:
        if session["token"]:
            dhan = dhanhq(MY_CLIENT_ID, session["token"])
            today = datetime.now().strftime('%Y-%m-%d')
            
            for idx in INDICES:
                try:
                    response = dhan.get_option_chain(idx['id'], "IDX_I", today)
                    if response.get('status') == 'success':
                        for oc in response['data']['oc']:
                            # Check Call (CE) Smart Money
                            # We alert if Volume > 1 Lakh or OI > 50k (adjust as needed)
                            if oc['ce']['volume'] > 100000 or oc['ce']['oi'] > 50000:
                                send_block_alert(idx['name'], oc['strike_price'], "CE", 
                                               oc['ce']['last_price'], oc['ce']['oi'], oc['ce']['volume'])
                            
                            # Check Put (PE) Smart Money
                            if oc['pe']['volume'] > 100000 or oc['pe']['oi'] > 50000:
                                send_block_alert(idx['name'], oc['strike_price'], "PE", 
                                               oc['pe']['last_price'], oc['pe']['oi'], oc['pe']['volume'])
                    time.sleep(2)
                except: continue
        time.sleep(300) # Scan every 5 minutes

# --- 3. RAILWAY SERVER & STARTUP ---
app = Flask('')
@app.route('/')
def home(): return "Block Zenith is Live"

def run(): app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))

@bot.message_handler(func=lambda m: len(m.text) > 100)
def arm_bot(m):
    session["token"] = m.text
    bot.send_message(m.chat.id, "🏛️ Block Zenith Armed! Tracking Smart Money Flow.")

if __name__ == "__main__":
    Thread(target=run).start()
    Thread(target=block_zenith_scanner).start()
    bot.infinity_polling()