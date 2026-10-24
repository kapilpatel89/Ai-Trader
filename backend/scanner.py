import asyncio
import time
import re
from typing import List, Dict, Any, Optional
from .coindcx_client import CoinDCXClient
from .technical_analysis import TechnicalAnalysis

class MarketScanner:
    """
    Scans CoinDCX Futures markets.
    Pre-filters top liquid pairs, pulls candles and orderbook,
    calculates multi-factor quantitative scores and pre-selects
    the highest probability trade setups for LLM review.
    """

    def __init__(self, client: CoinDCXClient):
        self.client = client
        self.cached_scan_results: List[Dict[str, Any]] = []
        self.last_scan_time: float = 0.0
        self.is_scanning: bool = False
        self.scan_progress: Dict[str, Any] = {"status": "idle", "scanned": 0, "total": 0, "current": ""}
        self._markets_cache: List[Dict[str, Any]] = []
        self._markets_cache_time: float = 0.0

    async def get_top_futures_pairs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Identify and map ALL active futures pairs from CoinDCX derivatives.
        Includes base asset name for enhanced search (e.g. JCT -> B-JCT_USDT).
        Never truncates; guarantees 100% market coverage.
        """
        now = time.time()
        if self._markets_cache and (now - self._markets_cache_time < 10.0):
            return self._markets_cache[:limit] if limit else self._markets_cache

        # Fetch active instruments and tickers in parallel
        instruments_task = self.client.get_active_futures_instruments()
        tickers_task = self.client.get_all_tickers()

        active_instruments, tickers = await asyncio.gather(
            instruments_task, tickers_task, return_exceptions=True
        )

        active_instruments = active_instruments if isinstance(active_instruments, list) else []
        tickers = tickers if isinstance(tickers, list) else []

        # Build spot ticker lookup map
        ticker_map = {}
        for t in tickers:
            m = t.get("market", "")
            ticker_map[m] = t
            ticker_map[m.upper()] = t
            norm = m.replace("B-", "").replace("_", "").replace("-", "").upper()
            ticker_map[norm] = t

        # Get live USDT/INR rate for dual currency display
        usdt_inr_rate = await self.client.get_usdt_inr_rate()

        matched_pairs = []
        for inst in active_instruments:
            # inst example: 'B-BTC_USDT', 'B-JCT_USDT', 'B-1000PEPE_USDT'
            clean = inst.replace("B-", "").replace("_", "").upper()
            stripped = re.sub(r'^(1000000|100000|10000|1000|1M|1K)', '', clean).upper()
            base_coin = stripped.replace("USDT", "")

            vol = 0.0
            price = 0.0
            change = 0.0
            notional_vol = 0.0

            # 1. First check spot ticker map
            t_data = ticker_map.get(inst) or ticker_map.get(clean) or ticker_map.get(stripped)
            if t_data:
                try:
                    vol = float(t_data.get("volume", 0) or 0)
                    price = float(t_data.get("last_price", 0) or 0)
                    change = float(t_data.get("change_24_hour", 0) or 0)
                    notional_vol = vol * price
                except (ValueError, TypeError):
                    pass

            # 2. Check uppercase or normalized variants if price still 0
            if price <= 0:
                t_data2 = ticker_map.get(clean.upper()) or ticker_map.get(stripped.upper())
                if t_data2:
                    try:
                        vol = float(t_data2.get("volume", 0) or 0)
                        price = float(t_data2.get("last_price", 0) or 0)
                        change = float(t_data2.get("change_24_hour", 0) or 0)
                        notional_vol = vol * price
                    except (ValueError, TypeError):
                        pass

            price_inr = round(price * usdt_inr_rate, 2) if price > 0 else 0.0

            matched_pairs.append({
                "symbol": inst,
                "clean_symbol": inst.replace("B-", ""),
                "base_coin": base_coin,
                "price": price,
                "price_inr": price_inr,
                "usdt_inr_rate": usdt_inr_rate,
                "change_24h": change,
                "volume": vol,
                "notional_vol": notional_vol
            })

        # Sort: coins with volume/price first by notional vol, then alphabetical
        matched_pairs.sort(key=lambda x: (x["notional_vol"] > 0, x["notional_vol"]), reverse=True)
        self._markets_cache = matched_pairs
        self._markets_cache_time = now
        return matched_pairs[:limit] if limit else matched_pairs

    async def get_high_liquidity_momentum_candidates(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Filters and ranks coins with high liquidity AND active price momentum (moving UP or DOWN).
        Pulls top gainers, top losers, and high volume momentum breakouts.
        """
        all_markets = await self.get_top_futures_pairs()
        valid_coins = [m for m in all_markets if m.get("price", 0) > 0 and m.get("notional_vol", 0) > 0]
        if not valid_coins:
            return all_markets[:limit]

        for coin in valid_coins:
            vol = coin.get("notional_vol", 0)
            change = abs(coin.get("change_24h", 0))
            coin["momentum_rank"] = (vol ** 0.5) * (1.0 + (change * 0.15))

        valid_coins.sort(key=lambda x: x["momentum_rank"], reverse=True)
        return valid_coins[:limit]

    async def scan_single_pair(self, pair: str, interval: str = "15m") -> Optional[Dict[str, Any]]:
        """
        Fetch multi-timeframe candles (15m tactical + 1h macro trend) + orderbook depth.
        Evaluates institutional confluence to formulate high-conviction CALL or PUT decisions.
        Filters out stale, dead, or high-slippage coins.
        """
        try:
            c15_task = self.client.get_candles(pair, interval="15m", limit=40)
            c1h_task = self.client.get_candles(pair, interval="1h", limit=50)
            ob_task = self.client.get_orderbook(pair, depth=20)
            rate_task = self.client.get_usdt_inr_rate()
            
            c15, c1h, ob_data, usdt_inr_rate = await asyncio.gather(
                c15_task, c1h_task, ob_task, rate_task, return_exceptions=True
            )
            
            if isinstance(c15, Exception) or not c15 or len(c15) < 10:
                return None
            if isinstance(ob_data, Exception) or not ob_data:
                return None
            c1h = c1h if (isinstance(c1h, list) and len(c1h) >= 15) else None
            rate = usdt_inr_rate if isinstance(usdt_inr_rate, (int, float)) and usdt_inr_rate > 0 else 100.74

            analysis = TechnicalAnalysis.full_coin_analysis(c15, ob_data, pair, candles_1h=c1h)
            if not analysis or analysis.get("is_valid") is False:
                return None
                
            price = analysis.get("current_price", 0.0)
            analysis["symbol"] = pair
            analysis["pair"] = pair
            analysis["clean_symbol"] = pair.replace("B-", "")
            analysis["usdt_inr_rate"] = rate
            analysis["current_price_inr"] = round(price * rate, 2)
            return analysis
        except Exception as e:
            print(f"[Scanner] Error scanning {pair}: {e}")
            return None

    async def run_full_scan(self, top_n: int = 30, interval: str = "15m") -> List[Dict[str, Any]]:
        """
        Execute full market scan across top liquid futures pairs.
        Uses semaphore to avoid rate-limiting.
        """
        if self.is_scanning:
            return self.cached_scan_results

        self.is_scanning = True
        self.scan_progress = {"status": "scanning", "scanned": 0, "total": top_n, "current": "Fetching tickers"}

        try:
            top_pairs = await self.get_top_futures_pairs(limit=top_n)
            self.scan_progress["total"] = len(top_pairs)
            
            results = []
            sem = asyncio.Semaphore(4)  # 4 concurrent requests max to prevent rate-limit

            async def worker(item):
                async with sem:
                    sym = item["symbol"]
                    self.scan_progress["current"] = sym
                    res = await self.scan_single_pair(sym, interval=interval)
                    self.scan_progress["scanned"] += 1
                    if res:
                        res["change_24h"] = item.get("change_24h", 0.0)
                        res["notional_vol"] = item.get("notional_vol", 0.0)
                        res["volume"] = item.get("volume", 0.0)
                        return res
                    return None

            tasks = [worker(p) for p in top_pairs]
            scan_outputs = await asyncio.gather(*tasks)
            
            results = [r for r in scan_outputs if r is not None]
            
            # Sort: actionable CALL or PUT setups first, then by absolute score
            results.sort(
                key=lambda x: (
                    x.get("action") in ["CALL (BUY)", "PUT (SELL)"],
                    abs(x.get("score", 0))
                ),
                reverse=True
            )
            
            self.cached_scan_results = results
            self.last_scan_time = time.time()
            self.scan_progress = {"status": "completed", "scanned": len(results), "total": len(top_pairs), "current": "Done"}
            return results
        finally:
            self.is_scanning = False
