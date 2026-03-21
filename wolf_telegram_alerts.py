#!/usr/bin/env python3
"""
📱 WOLF TELEGRAM ALERTER v2
Reads Wolf Pack v9 data and sends clean digest to Telegram.
Runs every 30 min via cron (offset from main scanner).
"""

import json
import os
import glob
from datetime import datetime

BOT_TOKEN = os.getenv("WOLF_MAIN_TOKEN", "")  # @wolf_quant_bot
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MIN_SCORE = 80
MAX_ALERTS = 5

def send_telegram(message: str) -> bool:
    import requests
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def check_and_send():
    # Find latest wolf alert file
    files = glob.glob("/tmp/wolf_alerts_*.json")
    if not files:
        print("No alert files found")
        return

    latest_file = max(files, key=os.path.getctime)

    # Dedup check — don't resend same file
    sent_marker = f"/tmp/.wolf_sent_{os.path.basename(latest_file)}"
    if os.path.exists(sent_marker):
        print(f"Already sent: {latest_file}")
        return

    with open(latest_file, 'r') as f:
        data = json.load(f)

    alerts = data if isinstance(data, list) else data.get('alerts', [])
    high_confidence = [a for a in alerts if a.get('score', 0) >= MIN_SCORE]

    if not high_confidence:
        print(f"No alerts >= {MIN_SCORE} score")
        open(sent_marker, 'w').close()
        return

    print(f"🚨 {len(high_confidence)} HIGH-CONFIDENCE ALERTS!")

    timestamp = datetime.now().strftime("%H:%M")
    msg = f"🐺 *WOLF ALERTS - {timestamp}*\n\n"
    msg += f"Found *{len(high_confidence)}* high-confidence signals:\n\n"

    for alert in high_confidence[:MAX_ALERTS]:
        contract = alert.get('token_address') or alert.get('address', '')
        symbol = alert.get('symbol', '?')
        score = alert.get('score', 0)
        price = alert.get('price', 0)
        change_5m = alert.get('price_change_5m', 0)
        change_1h = alert.get('price_change_1h', 0)
        change_24h = alert.get('price_change_24h', 0)
        volume = alert.get('volume_24h', 0)
        chain = alert.get('chain', 'solana').upper()
        cielo_url = f"https://app.cielo.finance/trading/{contract}?ref=iseeiape"

        msg += f"🔥 *${symbol}* - Score: {score}/100 | {chain}\n"
        msg += f"💰 Price: ${price:.8f}\n"
        msg += f"📊 5m: {change_5m:+.1f}% | 1h: {change_1h:+.1f}% | 24h: {change_24h:+.1f}%\n"
        msg += f"💧 Vol: ${volume:,.0f}\n"
        msg += f"📍 Contract: `{contract}`\n"
        msg += f"🔗 [Trade on Cielo]({cielo_url})\n\n"

    msg += "_Check DexScreener before buying! DYOR 🦎_"

    if send_telegram(msg):
        print(f"✅ Sent {min(len(high_confidence), MAX_ALERTS)} alerts to Telegram")
        open(sent_marker, 'w').close()
    else:
        print("❌ Failed to send")

if __name__ == "__main__":
    check_and_send()
