#!/usr/bin/env python3
"""
Wolf Performance Tracker
Track alert performance in SQLite and generate daily reports.
"""

import sqlite3
import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

DB_PATH = '/home/matrix/.openclaw/workspace/wolf_performance.db'
MAIN_BOT_TOKEN = "***REMOVED***"
MAIN_BOT_CHAT_ID = "***REMOVED***"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT NOT NULL,
            address         TEXT,
            chain           TEXT,
            score           INTEGER,
            category        TEXT,
            alert_type      TEXT,
            price_at_alert  REAL,
            mcap            REAL,
            volume_24h      REAL,
            timestamp       REAL NOT NULL,
            price_1h        REAL,
            price_4h        REAL,
            price_24h       REAL,
            return_1h       REAL,
            return_4h       REAL,
            return_24h      REAL,
            checked_at      REAL,
            signals         TEXT
        )
    ''')
    conn.commit()
    conn.close()


def log_alert(alert_data: Dict) -> Optional[int]:
    """Log a sent alert to the DB. Returns inserted row id."""
    init_db()
    conn = _get_db()
    try:
        signals = alert_data.get('signals', [])
        if isinstance(signals, list):
            signals = json.dumps(signals)

        cur = conn.execute('''
            INSERT INTO alerts
                (symbol, address, chain, score, category, alert_type,
                 price_at_alert, mcap, volume_24h, timestamp, signals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert_data.get('symbol', 'UNKNOWN'),
            alert_data.get('address', ''),
            alert_data.get('chain', 'solana'),
            alert_data.get('score', 0),
            alert_data.get('category', 'unknown'),
            alert_data.get('alert_type', ''),
            alert_data.get('price', 0),
            alert_data.get('market_cap', 0),
            alert_data.get('volume_24h', 0),
            time.time(),
            signals,
        ))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"❌ log_alert error: {e}")
        return None
    finally:
        conn.close()


def _fetch_current_price(address: str, chain: str) -> Optional[float]:
    """Fetch current price from DexScreener by token address."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            pairs = r.json().get('pairs', [])
            chain_pairs = [p for p in pairs if p.get('chainId') == chain]
            if chain_pairs:
                chain_pairs.sort(
                    key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0),
                    reverse=True,
                )
                return float(chain_pairs[0].get('priceUsd', 0) or 0)
    except Exception as e:
        print(f"⚠️  Price fetch error for {address}: {e}")
    return None


def update_prices():
    """
    Update price_1h / price_4h / price_24h for all alerts < 24h old
    that have not been checked in the last hour.
    """
    init_db()
    conn = _get_db()
    now = time.time()
    cutoff_24h = now - 86400
    rechecked_before = now - 3600  # avoid spamming within 1h

    try:
        rows = conn.execute('''
            SELECT id, symbol, address, chain, price_at_alert, timestamp,
                   price_1h, price_4h, price_24h, checked_at
            FROM alerts
            WHERE timestamp > ?
              AND (checked_at IS NULL OR checked_at < ?)
        ''', (cutoff_24h, rechecked_before)).fetchall()

        print(f"📊 Updating prices for {len(rows)} alerts…")
        updated = 0

        for row in rows:
            row_id = row['id']
            entry_price = row['price_at_alert']
            ts = row['timestamp']
            address = row['address']
            chain = row['chain'] or 'solana'

            if not address or not entry_price or entry_price <= 0:
                conn.execute('UPDATE alerts SET checked_at = ? WHERE id = ?', (now, row_id))
                continue

            current_price = _fetch_current_price(address, chain)
            if not current_price or current_price <= 0:
                conn.execute('UPDATE alerts SET checked_at = ? WHERE id = ?', (now, row_id))
                continue

            age = now - ts
            updates: Dict[str, Any] = {}

            if age >= 3600 and row['price_1h'] is None:
                ret = (current_price - entry_price) / entry_price * 100
                updates['price_1h'] = current_price
                updates['return_1h'] = ret

            if age >= 14400 and row['price_4h'] is None:
                ret = (current_price - entry_price) / entry_price * 100
                updates['price_4h'] = current_price
                updates['return_4h'] = ret

            if age >= 86400 and row['price_24h'] is None:
                ret = (current_price - entry_price) / entry_price * 100
                updates['price_24h'] = current_price
                updates['return_24h'] = ret

            if updates:
                set_clause = ', '.join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [now, row_id]
                conn.execute(
                    f'UPDATE alerts SET {set_clause}, checked_at = ? WHERE id = ?',
                    vals,
                )
                updated += 1
            else:
                conn.execute('UPDATE alerts SET checked_at = ? WHERE id = ?', (now, row_id))

            time.sleep(0.25)  # gentle rate limiting

        conn.commit()
        print(f"✅ Price update done — {updated} rows updated")
    except Exception as e:
        print(f"❌ update_prices error: {e}")
    finally:
        conn.close()


def generate_report() -> str:
    """Build a Telegram-ready performance report string."""
    init_db()
    conn = _get_db()
    now = time.time()
    week_ago = now - 7 * 86400

    try:
        # Overall stats
        overall = conn.execute('''
            SELECT COUNT(*) as total,
                   AVG(return_1h) as avg_return,
                   SUM(CASE WHEN return_1h >= 20 THEN 1 ELSE 0 END) as wins,
                   COUNT(return_1h) as checked
            FROM alerts
            WHERE timestamp > ?
        ''', (week_ago,)).fetchone()

        total_alerts = overall['total'] or 0
        total_checked = overall['checked'] or 0
        total_wins = overall['wins'] or 0
        avg_return = overall['avg_return'] or 0.0
        win_rate = (total_wins / total_checked * 100) if total_checked > 0 else 0

        # Per-category stats
        cat_rows = conn.execute('''
            SELECT category,
                   COUNT(*) as total,
                   AVG(return_1h) as avg_return_1h,
                   SUM(CASE WHEN return_1h >= 20 THEN 1 ELSE 0 END) as wins_1h,
                   COUNT(return_1h) as checked_1h
            FROM alerts
            WHERE timestamp > ?
            GROUP BY category
            ORDER BY avg_return_1h DESC
        ''', (week_ago,)).fetchall()

        # Top 5 performers
        top5 = conn.execute('''
            SELECT symbol, category, score, return_1h, timestamp
            FROM alerts
            WHERE timestamp > ? AND return_1h IS NOT NULL
            ORDER BY return_1h DESC
            LIMIT 5
        ''', (week_ago,)).fetchall()

        # Worst 5
        worst5 = conn.execute('''
            SELECT symbol, category, score, return_1h, timestamp
            FROM alerts
            WHERE timestamp > ? AND return_1h IS NOT NULL
            ORDER BY return_1h ASC
            LIMIT 5
        ''', (week_ago,)).fetchall()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        lines = [
            f"<b>🐺 WOLF DAILY PERFORMANCE REPORT</b>",
            f"{now_str}",
            "",
            f"<b>📊 Weekly Overview (7 days)</b>",
            f"Total Alerts: {total_alerts}",
            f"With 1h data: {total_checked}",
            f"Win Rate (+20% in 1h): {win_rate:.1f}%",
            f"Avg 1h Return: {avg_return:+.1f}%",
        ]

        if cat_rows:
            lines.append("")
            lines.append("<b>📈 By Category:</b>")
            for r in cat_rows:
                cat = r['category'] or 'unknown'
                chk = r['checked_1h'] or 0
                w = r['wins_1h'] or 0
                wr = (w / chk * 100) if chk > 0 else 0
                avg = r['avg_return_1h'] or 0.0
                lines.append(
                    f"• <b>{cat}</b>: {wr:.0f}% win rate, "
                    f"{avg:+.1f}% avg ({r['total']} alerts)"
                )

        if top5:
            lines.append("")
            lines.append("<b>🏆 Top 5 This Week:</b>")
            for r in top5:
                dt = datetime.fromtimestamp(r['timestamp']).strftime('%m/%d %H:%M')
                lines.append(
                    f"• {r['symbol']} ({r['category']}) — "
                    f"+{r['return_1h']:.1f}% [{r['score']}pts] @ {dt}"
                )

        if worst5:
            lines.append("")
            lines.append("<b>📉 Worst 5 (Learn From):</b>")
            for r in worst5:
                dt = datetime.fromtimestamp(r['timestamp']).strftime('%m/%d %H:%M')
                ret = r['return_1h'] or 0.0
                lines.append(
                    f"• {r['symbol']} ({r['category']}) — "
                    f"{ret:+.1f}% [{r['score']}pts] @ {dt}"
                )

        lines.append("")
        lines.append("#WolfPerformance")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error generating report: {e}"
    finally:
        conn.close()


def send_daily_report() -> bool:
    """Send the daily report via WOLF MAIN bot."""
    report = generate_report()
    url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': MAIN_BOT_CHAT_ID,
        'text': report,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Daily report sent via WOLF MAIN bot")
            return True
        else:
            print(f"❌ Report send failed: {r.status_code} — {r.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Report send error: {e}")
        return False


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: wolf_performance_tracker.py [update|report|send_report]")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == 'update':
        update_prices()
    elif cmd == 'report':
        print(generate_report())
    elif cmd == 'send_report':
        send_daily_report()
    else:
        print(f"Unknown command: {cmd}")
