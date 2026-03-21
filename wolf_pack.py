#!/usr/bin/env python3
"""
🐺🐺🐺🐺 WOLF PACK v9.0 - ENHANCED SCORING + PERFORMANCE TRACKER
- Short-term momentum scoring (5m/1h weighted)
- Major coin exclusion list + mcap ceiling
- Category-aware scoring per bot
- Integrated performance tracking
"""

import requests
import os
import json
import time
from datetime import datetime
import hashlib
from typing import Dict, List, Optional, Any, Tuple
import threading
from collections import defaultdict

# Import enhanced cache
try:
    from wolf_cache_enhanced import get_enhanced_cache
    print("✅ Using enhanced cache system")
except ImportError:
    from wolf_cache_fallback import WolfCacheFallback
    print("✅ Using basic cache (enhanced not available)")

# Import performance tracker (optional — degrades gracefully if missing)
try:
    from wolf_performance_tracker import log_alert as _track_log_alert
    from wolf_performance_tracker import send_daily_report as _track_daily_report
    from wolf_performance_tracker import update_prices as _track_update_prices
    _TRACKER_AVAILABLE = True
    print("✅ Performance tracker loaded")
except ImportError:
    _TRACKER_AVAILABLE = False
    print("⚠️  Performance tracker not available")

# ═══════════════════════════════════════════════════════════
# BOT CONFIGURATION - WOLF PACK v9.0
# ═══════════════════════════════════════════════════════════

BOTS = {
    'alpha': {
        'token': os.getenv("WOLF_ALPHA_TOKEN", ""),  # @wolf_quant_alpha_bot
        'chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
        'min_score': 90,
        'types': ['ALL'],
        'name': '🐺 WOLF ALPHA',
        'cooldown': 30,
        'category': 'alpha',
    },
    'newpairs': {
        'token': os.getenv("WOLF_NEWPAIRS_TOKEN", ""),  # @wolf_quant_newpairs_bot
        'chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
        'min_score': 0,
        'types': ['🆕 NEW_PAIR'],
        'name': '🆕 WOLF NEWPAIRS',
        'cooldown': 10,
        'category': 'newpairs',
    },
    'momentum': {
        'token': os.getenv("WOLF_MOMENTUM_TOKEN", ""),  # @wolf_quant_momentum_bot
        'chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
        'min_score': 70,
        'types': ['📈 TRENDING', '🚀 BREAKOUT', '📊 VOLUME_SPIKE'],
        'name': '📈 WOLF MOMENTUM',
        'cooldown': 15,
        'category': 'momentum',
    },
    'whale': {
        'token': os.getenv("WOLF_WHALE_TOKEN", ""),  # @wolf_quant_whale_bot
        'chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
        'min_score': 0,
        'types': ['💧 LIQUIDITY'],
        'min_volume': 500000,
        'name': '🐋 WOLF WHALE',
        'cooldown': 60,
        'category': 'whale',
    },
    'main': {
        'token': os.getenv("WOLF_MAIN_TOKEN", ""),  # @wolf_quant_bot
        'chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
        'min_score': 85,
        'types': ['ALL'],
        'name': '🐺 WOLF MAIN',
        'cooldown': 20,
        'category': 'alpha',
    }
}

# ═══════════════════════════════════════════════════════════
# EXCLUSION LISTS — skip known major / stable coins
# ═══════════════════════════════════════════════════════════

# Always skip these symbols regardless of mcap
EXCLUDED_SYMBOLS = {
    # Chain names appearing as token symbols (LP tokens, wrapped chain assets)
    'SOLANA', 'ETHEREUM', 'BASE', 'ARBITRUM', 'POLYGON', 'OPTIMISM', 'AVALANCHE',
    # Layer-1 natives
    'SOL', 'ETH', 'BTC', 'WBTC', 'WETH', 'cbBTC',
    'BNB', 'WBNB', 'AVAX', 'MATIC', 'POL', 'FTM', 'NEAR',
    'APT', 'SUI', 'SEI', 'TIA', 'INJ', 'OSMO', 'ATOM',
    'DOT', 'ADA', 'XRP', 'LTC', 'BCH', 'ETC',
    # Stablecoins
    'USDC', 'USDT', 'DAI', 'BUSD', 'FRAX', 'USDS', 'USDP',
    'TUSD', 'PYUSD', 'LUSD', 'crvUSD', 'GUSD', 'USDE',
    # Major DeFi / DEX tokens
    'UNI', 'AAVE', 'LINK', 'MKR', 'CRV', 'COMP', 'SNX', 'BAL',
    'YFI', 'SUSHI', '1INCH', 'LDO', 'RPL', 'PENDLE',
    # Major Solana ecosystem
    'RAY', 'JUP', 'BONK', 'WIF', 'PYTH', 'JTO', 'RNDR',
    # L2 tokens
    'ARB', 'OP', 'STRK', 'MANTA', 'ZK',
    # Wrapped / bridged
    'BRETT', 'CBETH', 'STETH', 'RETH', 'WSOL',
}

# Symbols that are sometimes on DEXes but are large-cap majors
# Skip if mcap exceeds KNOWN_MAJOR_MCAP_THRESHOLD
KNOWN_MAJORS = EXCLUDED_SYMBOLS  # same set, mcap is extra check

# Mcap thresholds
LARGE_CAP_MCAP_THRESHOLD = 500_000_000   # always skip above $500M mcap
KNOWN_MAJOR_MCAP_THRESHOLD = 50_000_000  # skip known majors above $50M

# ═══════════════════════════════════════════════════════════
# DATA SOURCE CONFIGURATIONS
# ═══════════════════════════════════════════════════════════

DATA_SOURCES = {
    'dexscreener': {
        'enabled': True,
        'api_url': 'https://api.dexscreener.com/latest/dex/search',
        'cache_ttl': 30,
        'chains': ['solana', 'base'],
        'priority': 1,
    },
    'coingecko': {
        'enabled': True,
        'api_url': 'https://api.coingecko.com/api/v3',
        'cache_ttl': 300,
        'requires_key': False,
        'priority': 2,
        'endpoints': {
            'markets': '/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false',
            'trending': '/search/trending',
            'global': '/global',
        }
    },
    'coinpaprika': {
        'enabled': True,
        'api_url': 'https://api.coinpaprika.com/v1',
        'cache_ttl': 300,
        'requires_key': False,
        'priority': 3,
        'endpoints': {
            'tickers': '/tickers',
            'global': '/global',
            'exchanges': '/exchanges',
        }
    },
    'binance': {
        'enabled': True,
        'api_url': 'https://api.binance.com/api/v3',
        'cache_ttl': 60,
        'requires_key': False,
        'priority': 4,
        'endpoints': {
            'ticker': '/ticker/24hr',
            'klines': '/klines',
            'depth': '/depth',
        }
    },
    'birdeye': {
        'enabled': False,
        'api_url': 'https://public-api.birdeye.so/public',
        'cache_ttl': 60,
        'requires_key': True,
        'priority': 5,
    },
    'helius': {
        'enabled': False,
        'api_url': 'https://api.helius.xyz/v0',
        'cache_ttl': 300,
        'requires_key': True,
        'priority': 6,
    }
}


class WolfPackV8Enhanced:
    """Wolf Pack v9 — enhanced scoring, major-coin filter, performance tracking."""

    def __init__(self):
        self.cache = get_enhanced_cache()
        self.stats = {
            'alerts_sent': defaultdict(int),
            'api_calls': defaultdict(int),
            'data_source_calls': defaultdict(int),
            'start_time': time.time(),
            'last_alert_time': defaultdict(float),
            'total_alerts': 0,
            'errors': 0,
        }
        self.alert_history = []
        self.max_history = 1000

        print("🐺 WOLF PACK v9.0 Enhanced Initialized")
        print(f"🚫 Excluded symbols: {len(EXCLUDED_SYMBOLS)}")
        print(f"📊 Data sources: {len([ds for ds in DATA_SOURCES if DATA_SOURCES[ds]['enabled']])} enabled")

        self.monitor_thread = threading.Thread(target=self._monitor_performance, daemon=True)
        self.monitor_thread.start()

    # ─────────────────────────────────────────────────────────
    # SYSTEM MONITORING
    # ─────────────────────────────────────────────────────────

    def _monitor_performance(self):
        while True:
            time.sleep(300)
            self._log_performance()

    def _log_performance(self):
        uptime = time.time() - self.stats['start_time']
        total_api = sum(self.stats['api_calls'].values())
        total_alts = sum(self.stats['alerts_sent'].values())

        print(f"\n📈 WOLF PACK PERFORMANCE ({datetime.now().strftime('%H:%M:%S')})")
        print(f"⏱️  Uptime: {uptime/3600:.1f}h")
        print(f"📞 API Calls: {total_api} ({total_api/max(1, uptime/3600):.1f}/h)")
        print(f"🚨 Alerts Sent: {total_alts} ({total_alts/max(1, uptime/3600):.1f}/h)")
        print(f"📊 By bot: {dict(self.stats['alerts_sent'])}")
        print(f"🌐 By source: {dict(self.stats['data_source_calls'])}")
        cache_stats = self.cache.get_stats()
        print(f"💾 Cache: {cache_stats['hit_rate']:.1%} hit rate, {cache_stats['cache_size_mb']:.2f} MB")

    # ─────────────────────────────────────────────────────────
    # API CALLS
    # ─────────────────────────────────────────────────────────

    def robust_api_call(self, url: str, source: str = 'unknown') -> Optional[Dict]:
        cache_key = f"api:{source}:{hashlib.md5(url.encode()).hexdigest()[:16]}"

        cached = self.cache.get('api_calls', cache_key)
        if cached is not None:
            self.stats['api_calls']['cache_hit'] += 1
            return cached

        self.stats['api_calls']['actual'] += 1
        self.stats['data_source_calls'][source] += 1

        for attempt in range(3):
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    ttl = DATA_SOURCES.get(source, {}).get('cache_ttl', 300)
                    self.cache.set('api_calls', cache_key, data, ttl_seconds=ttl)
                    return data
                elif response.status_code == 429:
                    wait = 2 ** attempt
                    print(f"⚠️  Rate limited ({source}), waiting {wait}s…")
                    time.sleep(wait)
                else:
                    print(f"❌ API error {response.status_code} for {source}")
                    break
            except Exception as e:
                print(f"❌ API call error ({source}, attempt {attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(1)

        self.stats['errors'] += 1
        return None

    def fetch_dexscreener_data(self, chain: str = 'solana') -> List[Dict]:
        if not DATA_SOURCES['dexscreener']['enabled']:
            return []
        pairs = []

        # 1. Token boosts (trending/paid promoted — high signal)
        boosts_data = self.robust_api_call(
            'https://api.dexscreener.com/token-boosts/latest/v1', 'dexscreener'
        )
        if isinstance(boosts_data, list):
            boost_addresses = [t.get('tokenAddress') for t in boosts_data
                               if t.get('chainId') == chain and t.get('tokenAddress')]
            # Fetch pair data for boosted tokens in batches of 30
            for i in range(0, min(len(boost_addresses), 60), 30):
                batch = ','.join(boost_addresses[i:i+30])
                data = self.robust_api_call(
                    f'https://api.dexscreener.com/latest/dex/tokens/{batch}', 'dexscreener'
                )
                if data and 'pairs' in data:
                    pairs.extend([p for p in data['pairs'] if p.get('chainId') == chain])

        # 2. New pairs on Solana via search (broader terms, not chain name)
        for query in ['pump', 'ai', 'meme', 'pepe', 'dog', 'cat', 'king']:
            data = self.robust_api_call(
                f'https://api.dexscreener.com/latest/dex/search?q={query}', 'dexscreener'
            )
            if data and 'pairs' in data:
                pairs.extend([p for p in data['pairs'] if p.get('chainId') == chain])

        # Deduplicate by pairAddress
        seen = set()
        unique = []
        for p in pairs:
            addr = p.get('pairAddress', '')
            if addr and addr not in seen:
                seen.add(addr)
                unique.append(p)

        return unique

    def fetch_coingecko_data(self) -> Dict[str, Any]:
        if not DATA_SOURCES['coingecko']['enabled']:
            return {}
        results = {}
        base = DATA_SOURCES['coingecko']['api_url']
        for key, ep in DATA_SOURCES['coingecko']['endpoints'].items():
            data = self.robust_api_call(f"{base}{ep}", 'coingecko')
            if data:
                results[key] = data
        return results

    def fetch_coinpaprika_data(self) -> Dict[str, Any]:
        if not DATA_SOURCES['coinpaprika']['enabled']:
            return {}
        results = {}
        base = DATA_SOURCES['coinpaprika']['api_url']
        for key, ep in DATA_SOURCES['coinpaprika']['endpoints'].items():
            data = self.robust_api_call(f"{base}{ep}", 'coinpaprika')
            if data:
                results[key] = data
        return results

    def fetch_binance_data(self) -> Dict[str, Any]:
        if not DATA_SOURCES['binance']['enabled']:
            return {}
        results = {}
        base = DATA_SOURCES['binance']['api_url']
        for key, ep in DATA_SOURCES['binance']['endpoints'].items():
            data = self.robust_api_call(f"{base}{ep}", 'binance')
            if data:
                results[key] = data
        return results

    # ─────────────────────────────────────────────────────────
    # SCORING HELPERS
    # ─────────────────────────────────────────────────────────

    def _calculate_score(
        self,
        price_change_5m: float,
        price_change_1h: float,
        price_change_24h: float,
        volume_5m: float,
        volume_1h: float,
        volume_24h: float,
        liquidity: float,
        buys_5m: int,
        sells_5m: int,
        buys_1h: int,
        sells_1h: int,
        pair_age_seconds: Optional[float],
        category: str = 'default',
    ) -> int:
        """
        New scoring system (max 100 pts):
          5m momentum     : 30 pts
          1h momentum     : 25 pts
          1h buy pressure : 20 pts
          liquidity       : 15 pts
          age bonus       : 10 pts
        """
        score = 0

        # ── 5m MOMENTUM (0-30) ──────────────────────────────
        if price_change_5m > 20:
            score += 30
        elif price_change_5m > 10:
            score += 25
        elif price_change_5m > 5:
            score += 20
        elif price_change_5m > 2:
            score += 15
        elif price_change_5m > 0.5:
            score += 10
        elif price_change_5m > 0:
            score += 5

        # ── 1h MOMENTUM (0-25) ──────────────────────────────
        if price_change_1h > 100:
            score += 25
        elif price_change_1h > 50:
            score += 22
        elif price_change_1h > 25:
            score += 18
        elif price_change_1h > 10:
            score += 14
        elif price_change_1h > 5:
            score += 10
        elif price_change_1h > 2:
            score += 5

        # ── 1h BUY PRESSURE (0-20) ──────────────────────────
        total_1h = buys_1h + sells_1h
        if total_1h > 0:
            buy_ratio_1h = buys_1h / total_1h
            if buy_ratio_1h > 0.80:
                score += 20
            elif buy_ratio_1h > 0.70:
                score += 16
            elif buy_ratio_1h > 0.65:
                score += 12
            elif buy_ratio_1h > 0.60:
                score += 8
            elif buy_ratio_1h > 0.55:
                score += 5
            elif buy_ratio_1h > 0.50:
                score += 3

        # ── LIQUIDITY (0-15) ────────────────────────────────
        if liquidity > 500_000:
            score += 15
        elif liquidity > 100_000:
            score += 12
        elif liquidity > 50_000:
            score += 9
        elif liquidity > 20_000:
            score += 6
        elif liquidity > 5_000:
            score += 3

        # ── AGE BONUS (0-10) ────────────────────────────────
        if pair_age_seconds is not None:
            if pair_age_seconds < 3_600:        # < 1h
                score += 10
            elif pair_age_seconds < 21_600:     # < 6h
                score += 7
            elif pair_age_seconds < 86_400:     # < 24h
                score += 4
            elif pair_age_seconds < 604_800:    # < 7d
                score += 1

        # ── CATEGORY-SPECIFIC ADJUSTMENTS ───────────────────
        if category == 'newpairs':
            # Brand-new pairs always qualify if age < 1h
            if pair_age_seconds is not None and pair_age_seconds < 3_600:
                score = max(score, 40)

        elif category == 'whale':
            # Volume bonus: whale bot cares about total volume
            if volume_24h > 2_000_000:
                score += 10
            elif volume_24h > 1_000_000:
                score += 7
            elif volume_24h > 500_000:
                score += 4

        elif category == 'momentum':
            # Extra credit for explosive 5m action
            if price_change_5m > 15 and (buys_5m + sells_5m) > 0:
                total_5m = buys_5m + sells_5m
                if buys_5m / total_5m > 0.65:
                    score += 5  # 5m confirmation bonus

        return min(score, 100)

    def _generate_signals(
        self, symbol, price_change_5m, price_change_1h, price_change_24h,
        volume_24h, liquidity, buys_5m, sells_5m, buys_1h, sells_1h,
        market_cap, total_24h,
    ) -> List[str]:
        signals = []
        total_5m = buys_5m + sells_5m

        if price_change_5m > 5:
            signals.append(f"⚡ 5m rocket: +{price_change_5m:.1f}%")
        if price_change_1h > 10:
            signals.append(f"📈 1h surge: +{price_change_1h:.1f}%")
        if price_change_24h > 50:
            signals.append(f"🔥 Daily moon: +{price_change_24h:.1f}% (24h)")

        if total_5m > 0 and buys_5m / total_5m > 0.65:
            signals.append(f"⚡ Heavy buying: {buys_5m} buys vs {sells_5m} sells (5m)")
        total_1h = buys_1h + sells_1h
        if total_1h > 0 and buys_1h / total_1h > 0.65:
            signals.append(f"💪 Buy pressure: {buys_1h} buys vs {sells_1h} sells (1h)")

        if volume_24h > 500_000:
            signals.append(f"💰 High volume: ${volume_24h:,.0f}")
        if liquidity > 50_000:
            signals.append(f"💧 Strong liquidity: ${liquidity:,.0f}")
        if 0 < market_cap < 1_000_000:
            signals.append(f"🎯 Micro cap gem: ${market_cap:,.0f}")
        elif market_cap < 10_000_000:
            signals.append(f"💎 Small cap: ${market_cap:,.0f}")

        if total_24h > 5_000:
            signals.append(f"🔥 Active trading: {total_24h:,} txns (24h)")

        return signals

    # ─────────────────────────────────────────────────────────
    # MAIN ANALYSIS
    # ─────────────────────────────────────────────────────────

    def analyze_pair(self, pair: Dict, category: str = 'default') -> Dict[str, Any]:
        """Analyze a DexScreener pair. Returns empty dict if excluded/filtered."""
        try:
            symbol = (pair.get('baseToken', {}).get('symbol', 'UNKNOWN') or 'UNKNOWN').upper()
            name = pair.get('baseToken', {}).get('name', 'Unknown Token') or 'Unknown Token'
            address = pair.get('pairAddress', '') or ''
            token_address = pair.get('baseToken', {}).get('address', '') or address
            chain = pair.get('chainId', 'solana') or 'solana'
            dex = pair.get('dexId', 'unknown') or 'unknown'

            # ── Exclusion checks ───────────────────────────
            if symbol in EXCLUDED_SYMBOLS:
                return {}

            price = float(pair.get('priceUsd', 0) or 0)

            # Multi-timeframe price changes
            price_change_5m = float(pair.get('priceChange', {}).get('m5', 0) or 0)
            price_change_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)
            price_change_24h = float(pair.get('priceChange', {}).get('h24', 0) or 0)

            # Volume
            volume_5m = float(pair.get('volume', {}).get('m5', 0) or 0)
            volume_1h = float(pair.get('volume', {}).get('h1', 0) or 0)
            volume_24h = float(pair.get('volume', {}).get('h24', 0) or 0)

            # Liquidity
            liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)

            # Market cap (DexScreener uses fdv or marketCap)
            market_cap = float(
                pair.get('fdv', 0) or pair.get('marketCap', 0) or 0
            )

            # ── Mcap filter ────────────────────────────────
            if market_cap > LARGE_CAP_MCAP_THRESHOLD:
                return {}
            if market_cap > KNOWN_MAJOR_MCAP_THRESHOLD and symbol in KNOWN_MAJORS:
                return {}

            # Transactions — multi-timeframe
            txns_5m = pair.get('txns', {}).get('m5', {}) or {}
            buys_5m = int(txns_5m.get('buys', 0) or 0)
            sells_5m = int(txns_5m.get('sells', 0) or 0)

            txns_1h = pair.get('txns', {}).get('h1', {}) or {}
            buys_1h = int(txns_1h.get('buys', 0) or 0)
            sells_1h = int(txns_1h.get('sells', 0) or 0)

            txns_24h = pair.get('txns', {}).get('h24', {}) or {}
            buys_24h = int(txns_24h.get('buys', 0) or 0)
            sells_24h = int(txns_24h.get('sells', 0) or 0)
            total_24h = buys_24h + sells_24h

            # Pair age
            pair_created_ms = pair.get('pairCreatedAt', 0) or 0
            pair_age_seconds: Optional[float] = None
            if pair_created_ms:
                pair_age_seconds = (time.time() * 1000 - pair_created_ms) / 1000

            # ── Score ──────────────────────────────────────
            score = self._calculate_score(
                price_change_5m=price_change_5m,
                price_change_1h=price_change_1h,
                price_change_24h=price_change_24h,
                volume_5m=volume_5m,
                volume_1h=volume_1h,
                volume_24h=volume_24h,
                liquidity=liquidity,
                buys_5m=buys_5m,
                sells_5m=sells_5m,
                buys_1h=buys_1h,
                sells_1h=sells_1h,
                pair_age_seconds=pair_age_seconds,
                category=category,
            )

            # ── Alert type ─────────────────────────────────
            alert_type = self._determine_alert_type(pair, score, pair_age_seconds)

            # ── Signals ────────────────────────────────────
            signals = self._generate_signals(
                symbol=symbol,
                price_change_5m=price_change_5m,
                price_change_1h=price_change_1h,
                price_change_24h=price_change_24h,
                volume_24h=volume_24h,
                liquidity=liquidity,
                buys_5m=buys_5m,
                sells_5m=sells_5m,
                buys_1h=buys_1h,
                sells_1h=sells_1h,
                market_cap=market_cap,
                total_24h=total_24h,
            )

            return {
                'symbol': symbol,
                'name': name,
                'address': address,
                'token_address': token_address,
                'chain': chain,
                'dex': dex,
                'price': price,
                'market_cap': market_cap,
                'price_change_5m': price_change_5m,
                'price_change_1h': price_change_1h,
                'price_change_24h': price_change_24h,
                'volume_5m': volume_5m,
                'volume_1h': volume_1h,
                'volume_24h': volume_24h,
                'liquidity': liquidity,
                'buys_5m': buys_5m,
                'sells_5m': sells_5m,
                'buys_1h': buys_1h,
                'sells_1h': sells_1h,
                'buys_24h': buys_24h,
                'sells_24h': sells_24h,
                'pair_age_seconds': pair_age_seconds,
                'score': score,
                'alert_type': alert_type,
                'signals': signals,
                'timestamp': time.time(),
                'pair_data': pair,
            }

        except Exception as e:
            print(f"❌ Error analyzing pair: {e}")
            return {}

    def _determine_alert_type(
        self, pair: Dict, score: int, pair_age_seconds: Optional[float]
    ) -> str:
        volume_24h = float(pair.get('volume', {}).get('h24', 0) or 0)
        price_change_24h = float(pair.get('priceChange', {}).get('h24', 0) or 0)
        price_change_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)
        liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
        volume_5m = float(pair.get('volume', {}).get('m5', 0) or 0)

        # New pair (< 24h old)
        if pair_age_seconds is not None and pair_age_seconds < 86_400:
            return '🆕 NEW_PAIR'

        # Volume spike: 5m volume is >5x the average 5-minute slice of 24h
        if volume_24h > 0 and volume_5m > (volume_24h / 288) * 5:
            return '📊 VOLUME_SPIKE'

        # Breakout: strong 1h move + meaningful volume
        if price_change_1h > 25 and volume_24h > 100_000:
            return '🚀 BREAKOUT'

        # Trending: consistent high volume + score
        if volume_24h > 500_000 and score > 70:
            return '📈 TRENDING'

        # Liquidity add: lots of liquidity but low volume
        if liquidity > 100_000 and volume_24h < 10_000:
            return '💧 LIQUIDITY'

        return '🔔 ALERT'

    # ─────────────────────────────────────────────────────────
    # TELEGRAM ALERTING
    # ─────────────────────────────────────────────────────────

    def send_telegram_alert(self, bot_name: str, analysis: Dict) -> bool:
        if not analysis:
            return False

        bot_config = BOTS.get(bot_name)
        if not bot_config:
            print(f"❌ Bot {bot_name} not found")
            return False

        # Cooldown check
        last_alert = self.stats['last_alert_time'].get(bot_name, 0)
        if time.time() - last_alert < bot_config.get('cooldown', 30):
            return False

        # Type check
        alert_type = analysis.get('alert_type', '')
        bot_types = bot_config.get('types', [])
        if 'ALL' not in bot_types and alert_type not in bot_types:
            # Exception: momentum bot also catches new pairs with strong 5m/1h momentum
            if bot_name == 'momentum' and alert_type == '🆕 NEW_PAIR':
                p5m = analysis.get('price_change_5m', 0)
                p1h = analysis.get('price_change_1h', 0)
                if p5m > 10 or p1h > 50:
                    pass  # allow through
                else:
                    return False
            else:
                return False

        # Score check — use category-adjusted score for this bot
        bot_category = bot_config.get('category', 'default')
        effective_score = analysis.get('score', 0)

        # For newpairs bot: also score with newpairs category weighting
        if bot_name == 'newpairs' and analysis.get('pair_age_seconds') is not None:
            pair_data = analysis.get('pair_data', {})
            if pair_data:
                np_analysis = self.analyze_pair(pair_data, category='newpairs')
                effective_score = np_analysis.get('score', effective_score)

        if effective_score < bot_config.get('min_score', 0):
            return False

        # Volume check for whale bot
        if bot_name == 'whale' and analysis.get('volume_24h', 0) < bot_config.get('min_volume', 0):
            return False

        # Send
        message = self._format_alert_message(analysis, bot_config['name'])
        token = bot_config['token']
        chat_id = bot_config['chat_id']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.stats['alerts_sent'][bot_name] += 1
                self.stats['total_alerts'] += 1
                self.stats['last_alert_time'][bot_name] = time.time()

                self.alert_history.append({
                    'timestamp': time.time(),
                    'bot': bot_name,
                    'symbol': analysis.get('symbol'),
                    'score': effective_score,
                    'type': alert_type,
                })
                if len(self.alert_history) > self.max_history:
                    self.alert_history = self.alert_history[-self.max_history:]

                print(f"✅ Alert sent via {bot_config['name']}: {analysis.get('symbol')} "
                      f"(score={effective_score}, type={alert_type})")

                # ── Performance tracking ───────────────────
                if _TRACKER_AVAILABLE:
                    try:
                        tracked = dict(analysis)
                        tracked['category'] = bot_category
                        _track_log_alert(tracked)
                    except Exception as te:
                        print(f"⚠️  Tracker log error: {te}")

                return True
            else:
                print(f"❌ Telegram error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Telegram send error: {e}")
            return False

    def _format_alert_message(self, analysis: Dict, bot_name: str) -> str:
        symbol = analysis.get('symbol', 'UNKNOWN')
        name = analysis.get('name', 'Unknown Token')
        chain = (analysis.get('chain', 'solana') or 'solana').upper()
        dex = (analysis.get('dex', 'unknown') or 'unknown').upper()
        price = analysis.get('price', 0)
        price_5m = analysis.get('price_change_5m', 0)
        price_1h = analysis.get('price_change_1h', 0)
        price_24h = analysis.get('price_change_24h', 0)
        volume = analysis.get('volume_24h', 0)
        liquidity = analysis.get('liquidity', 0)
        market_cap = analysis.get('market_cap', 0)
        score = analysis.get('score', 0)
        alert_type = analysis.get('alert_type', '🔔 ALERT')
        address = analysis.get('address', '')
        token_address = analysis.get('token_address', '') or address
        buys_5m = analysis.get('buys_5m', 0)
        sells_5m = analysis.get('sells_5m', 0)
        buys_1h = analysis.get('buys_1h', 0)
        sells_1h = analysis.get('sells_1h', 0)
        signals = analysis.get('signals', [])

        # Format numbers
        def fmt_usd(v):
            if v >= 1_000_000:
                return f"${v/1_000_000:.2f}M"
            elif v >= 1_000:
                return f"${v:,.0f}"
            elif v >= 1:
                return f"${v:.4f}"
            else:
                return f"${v:.8f}"

        price_str = fmt_usd(price)
        volume_str = fmt_usd(volume)
        liq_str = fmt_usd(liquidity)
        mcap_str = fmt_usd(market_cap) if market_cap > 0 else "unknown"

        change_1h_emoji = "📈" if price_1h > 0 else ("📉" if price_1h < 0 else "➖")
        change_24h_emoji = "📈" if price_24h > 0 else ("📉" if price_24h < 0 else "➖")

        score_emoji = "🔥" if score >= 90 else ("🚀" if score >= 80 else ("📈" if score >= 70 else "⚠️"))

        pair_age = analysis.get('pair_age_seconds')
        age_str = ""
        if pair_age is not None:
            if pair_age < 3600:
                age_str = f"\n<b>Age:</b> {int(pair_age/60)}m NEW"
            elif pair_age < 86400:
                age_str = f"\n<b>Age:</b> {pair_age/3600:.1f}h"

        signals_str = "\n".join(f"  • {s}" for s in signals[:5]) if signals else ""
        signals_block = f"\n<b>Signals:</b>\n{signals_str}" if signals_str else ""

        message = f"""<b>{bot_name} - {alert_type}</b>

<b>{symbol}</b> — {name}
{chain} • {dex}{age_str}

<b>Price:</b> {price_str}
<b>5m:</b> {price_5m:+.1f}%   <b>1h:</b> {change_1h_emoji} {price_1h:+.1f}%   <b>24h:</b> {change_24h_emoji} {price_24h:+.1f}%
<b>Txns (5m):</b> {buys_5m}B / {sells_5m}S   <b>(1h):</b> {buys_1h}B / {sells_1h}S

<b>Volume 24h:</b> {volume_str}
<b>Liquidity:</b> {liq_str}
<b>Market Cap:</b> {mcap_str}

<b>Wolf Score:</b> {score_emoji} <b>{score}/100</b>{signals_block}

<b>Links:</b>
• <a href="https://app.cielo.finance/trading/{token_address}?ref=iseeiape">🔗 Trade on Cielo</a>
• <a href="https://dexscreener.com/{chain.lower()}/{address}">DexScreener</a>
• <a href="https://www.geckoterminal.com/{chain.lower()}/pools/{address}">GeckoTerminal</a>

#WolfAlerts #{chain} #{symbol.replace('$', '')}"""
        return message.strip()

    # ─────────────────────────────────────────────────────────
    # SCAN
    # ─────────────────────────────────────────────────────────

    def run_scan(self, chains: List[str] = None):
        if chains is None:
            chains = ['solana', 'base']

        print(f"\n🔍 Starting scan at {datetime.now().strftime('%H:%M:%S')}")
        print(f"🌐 Chains: {', '.join(chains)}")

        all_pairs = []
        for chain in chains:
            print(f"  📡 Fetching {chain} data from DexScreener…")
            pairs = self.fetch_dexscreener_data(chain)
            all_pairs.extend(pairs)
            print(f"    ✅ {len(pairs)} pairs")
            time.sleep(1)

        if DATA_SOURCES['coingecko']['enabled']:
            cg = self.fetch_coingecko_data()
            if cg:
                print(f"  ✅ CoinGecko: {len(cg.get('markets', []))} coins")

        if DATA_SOURCES['coinpaprika']['enabled']:
            self.fetch_coinpaprika_data()
            print("  ✅ CoinPaprika fetched")

        if DATA_SOURCES['binance']['enabled']:
            self.fetch_binance_data()
            print("  ✅ Binance fetched")

        print(f"\n🔬 Analyzing {len(all_pairs)} pairs…")
        analyzed_pairs = []
        for pair in all_pairs:
            analysis = self.analyze_pair(pair)
            if analysis:
                analyzed_pairs.append(analysis)

        analyzed_pairs.sort(key=lambda x: x.get('score', 0), reverse=True)
        print(f"📊 {len(analyzed_pairs)} pairs passed filters")
        print("🏆 Top 5:")
        for i, a in enumerate(analyzed_pairs[:5], 1):
            age_info = ""
            if a.get('pair_age_seconds') is not None:
                age_info = f" age={a['pair_age_seconds']/3600:.1f}h"
            print(f"  {i}. {a.get('symbol'):8} Score:{a.get('score'):3} "
                  f"5m:{a.get('price_change_5m'):+.1f}% 1h:{a.get('price_change_1h'):+.1f}%"
                  f" {a.get('alert_type')}{age_info}")

        print(f"\n🚨 Sending alerts…")
        alerts_sent = 0
        for analysis in analyzed_pairs[:20]:
            if analysis.get('score', 0) < 50:
                break
            for bot_name in BOTS:
                if self.send_telegram_alert(bot_name, analysis):
                    alerts_sent += 1
                    time.sleep(0.5)

        print(f"✅ Scan complete: {alerts_sent} alerts sent")
        self._log_performance()

        # Write top alerts to the website repo for Vercel to serve
        self._write_wolf_live(analyzed_pairs[:20], len(all_pairs))

        # Also write /tmp/wolf_alerts_YYYYMMDD_HHMM.json (for wolf_telegram_alerts.py)
        self._write_tmp_alerts(analyzed_pairs, len(all_pairs))

        return {
            'total_pairs': len(all_pairs),
            'analyzed_pairs': len(analyzed_pairs),
            'alerts_sent': alerts_sent,
            'top_pairs': analyzed_pairs[:10],
            'timestamp': time.time(),
        }

    def _write_wolf_live(self, top_alerts: List[Dict], total_scanned: int):
        """Write scan results to website repo and auto-commit+push."""
        import subprocess
        website_dir = '/home/matrix/.openclaw/workspace/iseeiape-website'
        out_path = os.path.join(website_dir, 'data', 'wolf-live.json')
        now = datetime.now()

        normalized = []
        for a in top_alerts:
            addr = a.get('token_address') or a.get('address') or a.get('pairAddress') or ''
            normalized.append({
                'symbol': a.get('symbol', 'UNKNOWN'),
                'name': a.get('name', a.get('symbol', 'Unknown Token')),
                'score': a.get('score', 0),
                'alert_type': a.get('alert_type', 'SIGNAL'),
                'price': a.get('price', 0),
                'price_change_5m': a.get('price_change_5m', 0),
                'price_change_1h': a.get('price_change_1h', 0),
                'price_change_24h': a.get('price_change_24h', 0),
                'volume_24h': a.get('volume_24h', 0),
                'liquidity': a.get('liquidity', 0),
                'market_cap': a.get('market_cap', a.get('fdv', 0)),
                'pair_url': a.get('pair_url', f'https://dexscreener.com/solana/{addr}'),
                'token_address': addr,
                'chain': a.get('chain', 'solana'),
                'signals': a.get('signals', []),
                'timestamp': now.isoformat(),
            })

        payload = {
            'alerts': normalized,
            'lastUpdated': now.isoformat(),
            'totalScanned': total_scanned,
            'generatedAt': now.strftime('%H:%M'),
        }

        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            print(f"📁 Wrote {len(normalized)} alerts to {out_path}")

            commit_msg = f"Wolf alerts update {now.strftime('%H:%M')}"
            result = subprocess.run(
                f'cd {website_dir} && git add data/wolf-live.json && '
                f'git commit -m "{commit_msg}" && git push origin main',
                shell=True, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(f"🚀 Pushed wolf-live.json to repo")
            else:
                print(f"⚠️  Git push output: {result.stderr.strip() or result.stdout.strip()}")
        except Exception as e:
            print(f"⚠️  Failed to write wolf-live.json: {e}")

    def _write_tmp_alerts(self, analyzed_pairs: List[Dict], total_scanned: int):
        """Write /tmp/wolf_alerts_YYYYMMDD_HHMM.json for wolf_telegram_alerts.py compatibility."""
        now = datetime.now()
        path = f"/tmp/wolf_alerts_{now.strftime('%Y%m%d_%H%M')}.json"
        try:
            alerts = []
            for a in analyzed_pairs:
                addr = a.get('token_address') or a.get('address') or ''
                alerts.append({
                    'symbol': a.get('symbol', 'UNKNOWN'),
                    'name': a.get('name', ''),
                    'score': a.get('score', 0),
                    'alert_type': a.get('alert_type', 'SIGNAL'),
                    'price': a.get('price', 0),
                    'price_change_5m': a.get('price_change_5m', 0),
                    'price_change_1h': a.get('price_change_1h', 0),
                    'price_change_24h': a.get('price_change_24h', 0),
                    'volume_24h': a.get('volume_24h', 0),
                    'liquidity': a.get('liquidity', 0),
                    'market_cap': a.get('market_cap', 0),
                    'address': addr,
                    'token_address': addr,
                    'chain': a.get('chain', 'solana'),
                    'signals': a.get('signals', []),
                    'pair_url': a.get('pair_url', ''),
                })
            with open(path, 'w') as f:
                json.dump(alerts, f, indent=2)
            print(f"📄 Wrote {len(alerts)} alerts to {path}")
        except Exception as e:
            print(f"⚠️  Failed to write tmp alerts: {e}")

    # ─────────────────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────────────────

    def get_system_stats(self) -> Dict[str, Any]:
        uptime = time.time() - self.stats['start_time']
        cache_stats = self.cache.get_stats()
        cache_analytics = self.cache.get_analytics()
        return {
            'system': {
                'version': 'v9.0 Enhanced',
                'uptime_hours': uptime / 3600,
                'total_alerts': self.stats['total_alerts'],
                'errors': self.stats['errors'],
                'enabled_data_sources': [ds for ds in DATA_SOURCES if DATA_SOURCES[ds]['enabled']],
            },
            'alerts': {
                'by_bot': dict(self.stats['alerts_sent']),
                'total': self.stats['total_alerts'],
                'recent': self.alert_history[-10:] if self.alert_history else [],
            },
            'api': {
                'calls': dict(self.stats['api_calls']),
                'by_source': dict(self.stats['data_source_calls']),
                'total': sum(self.stats['api_calls'].values()),
            },
            'cache': cache_stats,
            'cache_analytics': cache_analytics,
            'timestamp': time.time(),
        }


# ═══════════════════════════════════════════════════════════
# CRON-READY HELPERS
# ═══════════════════════════════════════════════════════════

def run_hourly_price_update():
    """Call from cron every hour: updates alerted token prices in DB."""
    if _TRACKER_AVAILABLE:
        print(f"[{datetime.now().strftime('%H:%M')}] Running hourly price update…")
        _track_update_prices()
    else:
        print("⚠️  Performance tracker not available — skipping price update")


def run_daily_report():
    """Call from cron at 08:00 daily: sends performance report via WOLF MAIN."""
    if _TRACKER_AVAILABLE:
        print(f"[{datetime.now().strftime('%H:%M')}] Sending daily performance report…")
        _track_daily_report()
    else:
        print("⚠️  Performance tracker not available — skipping daily report")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print("""
    🐺🐺🐺🐺 WOLF PACK v9.0 ENHANCED 🐺🐺🐺🐺
    Short-term momentum scoring + performance tracking
    """)

    wolf_pack = WolfPackV8Enhanced()

    print("\n" + "=" * 60)
    print("🚀 INITIAL SYSTEM SCAN")
    print("=" * 60)

    scan_result = wolf_pack.run_scan()

    print("\n" + "=" * 60)
    print("📊 SYSTEM STATISTICS")
    print("=" * 60)

    stats = wolf_pack.get_system_stats()
    print(f"System: {stats['system']['version']}")
    print(f"Uptime: {stats['system']['uptime_hours']:.1f}h")
    print(f"Total Alerts: {stats['alerts']['total']}")
    print(f"API Calls: {stats['api']['total']}")
    print(f"Enabled Data Sources: {', '.join(stats['system']['enabled_data_sources'])}")
    print(f"Cache Hit Rate: {stats['cache'].get('hit_rate', 0):.1%}")
    print("\n✅ System ready")
    print("💡 Run wolf_pack.run_scan() for additional scans")
    print("💡 run_hourly_price_update() / run_daily_report() for tracking")


if __name__ == "__main__":
    main()
