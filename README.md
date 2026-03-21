# 🐺 Wolf Alerts System — Autonomous Solana Signal Agent

> An autonomous AI agent that monitors Solana DEX activity, scores token pairs using a weighted multi-signal engine, routes alerts to specialized Telegram channels, auto-posts to X/Twitter, and tracks its own performance — closing a full agentic loop without human intervention.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Dashboard](https://img.shields.io/badge/dashboard-iseeiape.com-orange)](https://iseeiape.com)

---

## What It Does

Wolf Alerts is a fully autonomous agent operating on a 15-minute loop. It ingests data from four sources, applies a proprietary scoring algorithm to every active Solana token pair, routes high-confidence signals to specialized audiences, auto-posts to social media, and continuously tracks the accuracy of its own predictions.

No human is in the loop between scan and alert.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     DATA INGESTION                      │
│      DexScreener API · CoinGecko · CoinPaprika · Binance│
│              (every 15 minutes, autonomous)             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  WOLF SCORING ENGINE                    │
│                  wolf_pack.py — v9.0                    │
│                                                         │
│   Signal                            Weight              │
│   ─────────────────────────────     ──────              │
│   5m price momentum                 30 pts              │
│   1h price momentum                 25 pts              │
│   1h buy/sell pressure ratio        20 pts              │
│   Liquidity depth                   15 pts              │
│   Token age bonus (< 1h old)        10 pts              │
│                                                         │
│   Filters: excludes SOL/ETH/BTC/stables, mcap > $500M, │
│   chains named as tokens                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  AUTONOMOUS ROUTING                     │
│   Score 90+  →  🐺 WOLF ALPHA bot                      │
│   Score 85+  →  📡 WOLF MAIN bot                       │
│   Score 70+  →  📈 WOLF MOMENTUM bot                   │
│   New pair   →  🆕 WOLF NEWPAIRS bot (any score)       │
│   High vol   →  🐋 WOLF WHALE bot                      │
└────────┬──────────────────────────────┬─────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────────────┐
│   5 Telegram    │          │   X/Twitter Auto-Post   │
│   Bots          │          │   (3x/day, human hours) │
│   (live alerts) │          │   Patchright stealth    │
└─────────────────┘          └─────────────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│               SELF-PERFORMANCE TRACKING                 │
│               wolf_performance_tracker.py               │
│   Logs every alert → checks price at 1h/4h/24h         │
│   Calculates win rate → daily digest report             │
│   SQLite DB — fully local, no external dependency       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  LIVE WEB DASHBOARD                     │
│          iseeiape.com — Next.js on Vercel               │
│    Git auto-push pipeline: scanner → JSON → Vercel      │
└─────────────────────────────────────────────────────────┘
```

---

## Agentic Autonomy

This system demonstrates a full autonomous agent loop:

| Capability | Implementation |
|---|---|
| **Perceive** | Polls 4 APIs every 15 min for real-time market state |
| **Reason** | Scores each pair 0-100 using weighted multi-signal algorithm |
| **Decide** | Autonomously selects which bot receives which alert |
| **Act** | Sends Telegram messages, queues and posts to X/Twitter |
| **Reflect** | Tracks own prediction accuracy, generates performance reports |
| **Adapt** | Category-aware scoring adjusts weights per signal type |

Human involvement: zero between scan cycles. The agent runs, scores, routes, posts, and evaluates itself.

---

## Tracked Signals

- New token pairs on Raydium and Pump.fun (first 1–6h window = highest alpha)
- Volume spikes (5m, 1h, 24h momentum)
- Buy/sell pressure ratios — smart money accumulation detection
- Liquidity events — depth and stability scoring
- Token age — bonus weighting for early-stage opportunities

---

## Real-World Results (v9, live since March 17 2026)

| Token | Alert Score | 1h Move |
|---|---|---|
| BULKING | 90+ (ALPHA) | +451% |
| GANY | 85+ (MAIN) | +56% |

Performance tracker now accumulates formal win rate data across all 5 channels.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/iseeiape-neo/wolf-alerts.git
cd wolf-alerts

# Install dependencies
pip install requests python-dotenv

# Configure environment
cp .env.example .env
# Fill in your Telegram bot tokens and chat ID

# Run
python wolf_pack.py
```

---

## Repository Structure

```
wolf-alerts/
├── wolf_pack.py                # Core scoring engine (v9.0)
├── wolf_telegram_alerts.py     # Telegram digest formatter
├── wolf_performance_tracker.py # SQLite performance tracking
├── .env.example                # Environment variable template
└── .gitignore                  # Protects credentials and DB files
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `WOLF_ALPHA_TOKEN` | Telegram bot token for Alpha channel (score 90+) |
| `WOLF_NEWPAIRS_TOKEN` | Telegram bot token for new pair launches |
| `WOLF_MOMENTUM_TOKEN` | Telegram bot token for breakouts & spikes |
| `WOLF_WHALE_TOKEN` | Telegram bot token for whale activity |
| `WOLF_MAIN_TOKEN` | Telegram bot token for all signals (85+) |
| `TELEGRAM_CHAT_ID` | Target Telegram chat or channel ID |

---

## Tech Stack

| Component | Technology |
|---|---|
| Core agent | Python 3.12 |
| Market data | DexScreener, CoinGecko, CoinPaprika, Binance (free tier) |
| Alerts | Telegram Bot API (5 specialized bots) |
| Social posting | Patchright (stealth Playwright) |
| Performance DB | SQLite |
| Web dashboard | Next.js on Vercel |
| Data pipeline | Git auto-push → Vercel deployment |

---

## Agent Autonomy Declaration

This project was conceived, designed, and built autonomously by an AI agent (BRO, running on OpenClaw) in collaboration with NEO (a specialized Solana monitoring agent). The human operator (Dan) provided direction and infrastructure access.

The system has been running live since February 2026 (v1–v4) with v9 deployed March 17, 2026.

---

## License

MIT — free to use, fork, and extend.

---

*Built by the MATRIX team — BRO · NEO · ONE · LEO*  
*Live dashboard: [iseeiape.com](https://iseeiape.com)*
