import time
import json
import re
import hmac
import hashlib
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional

class CoinDCXClient:
    """
    CoinDCX Futures API Client
    Handles public market data (active contracts, tickers, candles, orderbook)
    and authenticated trading endpoints (orders, positions, balances) with HMAC-SHA256.
    """
    PUBLIC_BASE_URL = "https://public.coindcx.com"
    API_BASE_URL = "https://api.coindcx.com"

    def __init__(self, api_key: str = "", secret_key: str = ""):
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_cache: Dict[str, float] = {}
        self._ticker_cache_time: float = 0.0

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CoinDCX-AI-Terminal/1.0"}
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, body_json: str) -> str:
        """Generate HMAC-SHA256 signature for private endpoints."""
        if not self.secret_key:
            return ""
        return hmac.new(
            self.secret_key.encode("utf-8"),
            body_json.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    # ==========================================================
    # Public Market Data
    # ==========================================================

    async def get_active_futures_instruments(self) -> List[str]:
        """
        Fetch all active futures contracts on CoinDCX.
        Returns list of symbols like ['B-BTC_USDT', 'B-ETH_USDT', ...]
        """
        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/data/active_instruments"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching active instruments: {e}")
            return []

    async def get_all_tickers(self) -> List[Dict[str, Any]]:
        """
        Fetch 24h ticker for all markets (price, 24h change, volume, high, low).
        """
        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/ticker"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching tickers: {e}")
            return []

    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """Fast lookup of current market price for any symbol with 1s cache."""
        now = time.time()
        if now - self._ticker_cache_time > 1.0 or not self._ticker_cache:
            try:
                tickers = await self.get_all_tickers()
                if tickers:
                    new_cache = {}
                    for item in tickers:
                        m = str(item.get("market", "")).upper()
                        lp = float(item.get("last_price", 0) or 0)
                        if lp > 0:
                            new_cache[m] = lp
                            clean = m.replace("B-", "").replace("_", "")
                            new_cache[clean] = lp
                            new_cache[m.replace("B-", "")] = lp
                    self._ticker_cache = new_cache
                    self._ticker_cache_time = now
            except Exception:
                pass

        sym_clean = symbol.upper().replace("B-", "").replace("_", "")
        if symbol.upper() in self._ticker_cache:
            return self._ticker_cache[symbol.upper()]
        if sym_clean in self._ticker_cache:
            return self._ticker_cache[sym_clean]
        if f"B-{symbol.upper()}" in self._ticker_cache:
            return self._ticker_cache[f"B-{symbol.upper()}"]
        return None

    async def get_candles(self, pair: str, interval: str = "1h", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candlesticks for a futures pair.
        Intervals: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 1d
        Returns list of {open, high, low, close, volume, time}
        Supports multiplier fallbacks (e.g. 1000PEPE -> PEPE).
        """
        session = await self.get_session()
        clean_pair = pair
        if not clean_pair.startswith("B-") and "_" in clean_pair:
            clean_pair = f"B-{clean_pair}"
        
        candidates = [clean_pair]
        stripped = re.sub(r'1000000|100000|10000|1000|1M|1K', '', clean_pair)
        if stripped != clean_pair:
            candidates.append(stripped)

        for p in candidates:
            url = f"{self.PUBLIC_BASE_URL}/market_data/candles/?pair={p}&interval={interval}&limit={limit}"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            data.sort(key=lambda x: x.get("time", 0))
                            return data
            except Exception:
                pass

        return []

    async def get_orderbook(self, pair: str, depth: int = 20) -> Dict[str, Any]:
        """
        Fetch order book depth for futures contract.
        pair: 'B-BTC_USDT' -> endpoint requires 'B-BTC_USDT-futures'
        depth: 10, 20, 50
        Supports multiplier fallbacks (e.g. 1000PEPE -> PEPE).
        """
        session = await self.get_session()
        clean_pair = pair
        if not clean_pair.startswith("B-") and "_" in clean_pair:
            clean_pair = f"B-{clean_pair}"

        candidates = [clean_pair]
        stripped = re.sub(r'1000000|100000|10000|1000|1M|1K', '', clean_pair)
        if stripped != clean_pair:
            candidates.append(stripped)

        for p in candidates:
            futures_p = p if p.endswith("-futures") else f"{p}-futures"
            url_v3 = f"{self.PUBLIC_BASE_URL}/market_data/v3/orderbook/{futures_p}/{depth}"
            try:
                async with session.get(url_v3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get("bids") and len(data.get("bids", {})) > 0:
                            return data
            except Exception:
                pass

            # Fallback to market_data/orderbook?pair=
            url_v1 = f"{self.PUBLIC_BASE_URL}/market_data/orderbook?pair={p}"
            try:
                async with session.get(url_v1) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get("bids") and len(data.get("bids", {})) > 0:
                            return data
            except Exception:
                pass

        return {}

    async def get_all_futures_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch 24h ticker data directly from CoinDCX.
        Returns a map: SYMBOL -> {last_price, change_24_hour, volume, notional_vol}
        """
        tickers = await self.get_all_tickers()
        ticker_map = {}
        for item in tickers:
            m = item.get("market", "").upper()
            try:
                last_price = float(item.get("last_price", 0) or 0)
                change_pct = float(item.get("change_24_hour", 0) or 0)
                vol = float(item.get("volume", 0) or 0)
                ticker_map[m] = {
                    "last_price": last_price,
                    "change_24_hour": change_pct,
                    "volume": vol,
                    "notional_vol": vol * last_price
                }
            except Exception:
                pass
        return ticker_map

    # ==========================================================
    # Live USDT / INR Conversion Rate
    # ==========================================================

    _cached_usdt_inr_rate: float = 100.74
    _last_usdt_inr_time: float = 0.0

    async def get_usdt_inr_rate(self) -> float:
        """Fetch live USDT/INR conversion rate with 15s caching."""
        now = time.time()
        if CoinDCXClient._cached_usdt_inr_rate > 0 and (now - CoinDCXClient._last_usdt_inr_time < 15.0):
            return CoinDCXClient._cached_usdt_inr_rate

        try:
            tickers = await self.get_all_tickers()
            for t in tickers:
                if t.get("market") == "USDTINR":
                    rate = float(t.get("last_price", 0) or 0)
                    if rate > 0:
                        CoinDCXClient._cached_usdt_inr_rate = rate
                        CoinDCXClient._last_usdt_inr_time = now
                        return rate
        except Exception as e:
            print(f"[CoinDCXClient] Error fetching USDTINR rate: {e}")

        return CoinDCXClient._cached_usdt_inr_rate

    # ==========================================================
    # Authenticated User & Profile Endpoints
    # ==========================================================

    async def get_user_info(self) -> Dict[str, Any]:
        """Fetch authenticated user profile details from CoinDCX."""
        if not self.api_key or not self.secret_key:
            return {"success": False, "error": "API Key and Secret Key are missing."}

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/users/info"
        body = {"timestamp": int(time.time() * 1000)}
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                    username = name or data.get("email") or data.get("coindcx_id") or "CoinDCX Trader"
                    return {
                        "success": True,
                        "username": username,
                        "first_name": data.get("first_name", ""),
                        "last_name": data.get("last_name", ""),
                        "email": data.get("email", ""),
                        "coindcx_id": data.get("coindcx_id", ""),
                        "mobile_number": data.get("mobile_number", ""),
                        "kyc_status": data.get("kyc_status", "verified"),
                        "raw": data
                    }
                text = await resp.text()
                try:
                    err_json = json.loads(text)
                    err_msg = err_json.get("message") or err_json.get("error") or text
                except Exception:
                    err_msg = text
                return {"success": False, "status_code": resp.status, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        """
        Comprehensive API validation:
        Tests credentials, queries user profile, fetches wallet balances,
        and returns complete verified account state.
        """
        if not self.api_key or not self.secret_key:
            return {
                "success": False,
                "authenticated": False,
                "message": "⚠️ API Key or Secret Key is not configured.",
                "guide": "Please enter your CoinDCX API Key and Secret Key in the settings modal to enable Live Trading."
            }

        user_info = await self.get_user_info()
        wallet = await self.get_inr_wallet_summary()
        positions = await self.get_futures_positions(margin_currency="INR")

        if not user_info.get("success"):
            err_text = user_info.get("error", "Unknown error")
            return {
                "success": False,
                "authenticated": False,
                "status_code": user_info.get("status_code", 401),
                "error": err_text,
                "message": f"❌ CoinDCX API Authentication Failed: {err_text}",
                "guide": "Check that your API Key and Secret are copied accurately from CoinDCX API Management and have Futures trading permissions enabled."
            }

        username = user_info.get("username", "Trader")
        inr_avail = wallet.get("inr_available", 0.0)
        usdt_avail = wallet.get("usdt_available", 0.0)
        total_inr = wallet.get("total_portfolio_inr", 0.0)

        return {
            "success": True,
            "authenticated": True,
            "username": username,
            "email": user_info.get("email", ""),
            "coindcx_id": user_info.get("coindcx_id", ""),
            "kyc_status": user_info.get("kyc_status", "verified"),
            "inr_balance": wallet.get("inr_balance", 0.0),
            "inr_available": inr_avail,
            "inr_locked": wallet.get("inr_locked", 0.0),
            "usdt_balance": wallet.get("usdt_balance", 0.0),
            "usdt_available": usdt_avail,
            "total_portfolio_inr": total_inr,
            "open_positions_count": len(positions),
            "futures_wallet": wallet.get("futures_wallet", {}),
            "spot_wallet": wallet.get("spot_wallet", {}),
            "options_wallet": wallet.get("options_wallet", {}),
            "message": f"✓ Live CoinDCX Connected: Welcome {username}! ₹{inr_avail:,.2f} available for futures trading (Total Margin: ₹{wallet.get('inr_balance', 0.0):,.2f}).",
            "guide": "CoinDCX Derivatives Futures wallet is active and synced as live trading balance for all INR orders and positions."
        }

    # ==========================================================
    # Authenticated Trading Endpoints (CoinDCX INR Futures & Spot)
    # ==========================================================

    async def get_futures_wallets(self) -> List[Dict[str, Any]]:
        """
        Fetch CoinDCX Derivatives Futures Wallets.
        Endpoint: GET /exchange/v1/derivatives/futures/wallets
        Returns list with INR and USDT futures wallets including balance, locked_balance, and margin.
        """
        if not self.api_key or not self.secret_key:
            return []

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/wallets"
        body = {"timestamp": int(time.time())}
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.get(url, data=body_json, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []
                text = await resp.text()
                print(f"[CoinDCX] Futures wallets error ({resp.status}): {text}")
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching futures wallets: {e}")
            return []

    async def get_user_balances(self) -> List[Dict[str, Any]]:
        """Fetch spot wallet balances from /exchange/v1/users/balances."""
        if not self.api_key or not self.secret_key:
            return []
        
        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/users/balances"
        body = {"timestamp": int(time.time() * 1000)}
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                text = await resp.text()
                print(f"[CoinDCX] Balances error ({resp.status}): {text}")
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching balances: {e}")
            return []

    async def get_inr_wallet_summary(self) -> Dict[str, Any]:
        """
        Extract live INR & USDT balances directly from CoinDCX Futures Wallet (Derivatives)
        and Spot Wallet. Prioritizes the Futures Wallet as the live trading margin.
        """
        futures_wallets = await self.get_futures_wallets()
        spot_balances = await self.get_user_balances()
        usdt_rate = await self.get_usdt_inr_rate()

        # 1. Futures Wallet (Derivatives margin for trading)
        fut_inr_total = 0.0
        fut_inr_locked = 0.0
        fut_inr_avail = 0.0
        fut_usdt_total = 0.0
        fut_usdt_locked = 0.0
        fut_usdt_avail = 0.0

        for fw in futures_wallets:
            cur = str(fw.get("currency_short_name", "")).upper()
            try:
                bal = float(fw.get("balance", 0) or 0)
                locked = float(fw.get("locked_balance", 0) or 0)
                cross_order = float(fw.get("cross_order_margin", 0) or 0)
                cross_user = float(fw.get("cross_user_margin", 0) or 0)
                tot_locked = locked + cross_order + cross_user
                avail = max(0.0, bal - tot_locked)
            except (ValueError, TypeError):
                bal, locked, avail = 0.0, 0.0, 0.0

            if cur == "INR":
                fut_inr_total = bal
                fut_inr_locked = tot_locked
                fut_inr_avail = avail
            elif cur == "USDT":
                fut_usdt_total = bal
                fut_usdt_locked = tot_locked
                fut_usdt_avail = avail

        # 2. Spot Wallet
        spot_inr_total = 0.0
        spot_inr_locked = 0.0
        spot_usdt_total = 0.0
        for b in spot_balances:
            cur = str(b.get("currency", "")).upper()
            try:
                bal = float(b.get("balance", 0) or 0)
                locked = float(b.get("locked_balance", 0) or 0)
            except (ValueError, TypeError):
                bal, locked = 0.0, 0.0

            if cur == "INR":
                spot_inr_total = bal
                spot_inr_locked = locked
            elif cur == "USDT":
                spot_usdt_total = bal

        # Fallback if futures wallets API returned empty, use spot
        if fut_inr_total <= 0 and fut_usdt_total <= 0 and (spot_inr_total > 0 or spot_usdt_total > 0):
            active_inr_total = spot_inr_total
            active_inr_locked = spot_inr_locked
            active_inr_avail = max(0.0, spot_inr_total - spot_inr_locked)
            active_usdt_total = spot_usdt_total
            active_usdt_avail = spot_usdt_total
            wallet_source = "SPOT_WALLET_FALLBACK"
        else:
            active_inr_total = fut_inr_total
            active_inr_locked = fut_inr_locked
            active_inr_avail = fut_inr_avail
            active_usdt_total = fut_usdt_total
            active_usdt_avail = fut_usdt_avail
            wallet_source = "FUTURES_DERIVATIVES"

        total_inr_net = active_inr_total + (active_usdt_total * usdt_rate)

        return {
            "currency": "INR",
            "currency_symbol": "₹",
            "usdt_inr_rate": usdt_rate,
            "inr_balance": round(active_inr_total, 2),
            "inr_locked": round(active_inr_locked, 2),
            "inr_available": round(active_inr_avail, 2),
            "usdt_balance": round(active_usdt_total, 4),
            "usdt_available": round(active_usdt_avail, 4),
            "total_portfolio_inr": round(total_inr_net, 2),
            "wallet_source": wallet_source,
            "futures_wallet": {
                "inr_balance": round(fut_inr_total, 2),
                "inr_locked": round(fut_inr_locked, 2),
                "inr_available": round(fut_inr_avail, 2),
                "usdt_balance": round(fut_usdt_total, 6),
                "usdt_available": round(fut_usdt_avail, 6)
            },
            "spot_wallet": {
                "inr_balance": round(spot_inr_total, 2),
                "inr_available": round(max(0.0, spot_inr_total - spot_inr_locked), 2),
                "usdt_balance": round(spot_usdt_total, 4)
            },
            "options_wallet": {
                "status": "Segregated Sub-Wallet",
                "note": "CoinDCX Options trading uses an isolated sub-wallet. Funds can be transferred via CoinDCX App/Web."
            }
        }

    async def get_all_currency_balances(self) -> Dict[str, Any]:
        """
        Fetch all currency balances from CoinDCX Futures and Spot wallets,
        calculate INR/USDT equivalent, and return comprehensive list.
        """
        futures_wallets = await self.get_futures_wallets()
        spot_balances = await self.get_user_balances()
        usdt_rate = await self.get_usdt_inr_rate()
        
        result_list = []
        total_inr = 0.0

        # 1. Futures Wallets (Priority live trading margins)
        for fw in futures_wallets:
            cur = str(fw.get("currency_short_name", "")).upper()
            try:
                bal = float(fw.get("balance", 0) or 0)
                locked = float(fw.get("locked_balance", 0) or 0)
                cross_order = float(fw.get("cross_order_margin", 0) or 0)
                cross_user = float(fw.get("cross_user_margin", 0) or 0)
                tot_locked = locked + cross_order + cross_user
                avail = max(0.0, bal - tot_locked)
            except (ValueError, TypeError):
                bal, locked, avail = 0.0, 0.0, 0.0

            val_inr = bal if cur == "INR" else (bal * usdt_rate)
            total_inr += val_inr

            result_list.append({
                "currency": cur,
                "label": f"{cur} (Futures Margin)",
                "wallet_type": "Futures Trading Wallet",
                "wallet_badge": "FUTURES",
                "balance": round(bal, 4 if cur == "INR" else 6),
                "locked": round(tot_locked, 4 if cur == "INR" else 6),
                "available": round(avail, 4 if cur == "INR" else 6),
                "value_inr": round(val_inr, 2),
                "value_usdt": round(val_inr / usdt_rate, 2) if usdt_rate > 0 else 0.0,
                "is_trading_margin": True
            })

        # 2. Spot Balances
        for b in spot_balances:
            cur = str(b.get("currency", "")).upper()
            try:
                bal = float(b.get("balance", 0) or 0)
                locked = float(b.get("locked_balance", 0) or 0)
            except (ValueError, TypeError):
                bal, locked = 0.0, 0.0
            
            avail = max(0.0, bal - locked)
            if bal <= 0 and locked <= 0:
                continue

            val_inr = 0.0
            if cur == "INR":
                val_inr = bal
            elif cur == "USDT":
                val_inr = bal * usdt_rate
            else:
                coin_price = await self.get_latest_price(f"{cur}USDT") or await self.get_latest_price(f"{cur}_USDT") or 0.0
                if coin_price > 0:
                    val_inr = bal * coin_price * usdt_rate

            total_inr += val_inr

            result_list.append({
                "currency": cur,
                "label": f"{cur} (Spot)",
                "wallet_type": "Spot Wallet",
                "wallet_badge": "SPOT",
                "balance": round(bal, 6),
                "locked": round(locked, 6),
                "available": round(avail, 6),
                "value_inr": round(val_inr, 2),
                "value_usdt": round(val_inr / usdt_rate, 2) if usdt_rate > 0 else 0.0,
                "is_trading_margin": False
            })

        result_list.sort(key=lambda x: x["value_inr"], reverse=True)

        return {
            "success": True,
            "balances": result_list,
            "total_portfolio_inr": round(total_inr, 2),
            "total_portfolio_usdt": round(total_inr / usdt_rate, 2) if usdt_rate > 0 else 0.0,
            "usdt_inr_rate": usdt_rate
        }

    async def get_futures_positions(self, margin_currency: str = "INR", only_active: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch current open futures positions for specified margin currency ('INR' or 'USDT').
        When only_active=True, strictly filters out closed/zero-quantity historical position records.
        """
        if not self.api_key or not self.secret_key:
            return []

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/positions"
        body = {
            "timestamp": int(time.time() * 1000),
            "margin_currency_short_name": [margin_currency.upper()]
        }
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not isinstance(data, list):
                        return []
                    
                    if not only_active:
                        return data

                    # Strictly filter for CURRENTLY RUNNING positions only
                    rate = await self.get_usdt_inr_rate()
                    active_positions = []
                    for p in data:
                        active_pos = float(p.get("active_pos", 0) or 0)
                        locked_margin = float(p.get("locked_margin", 0) or p.get("locked_user_margin", 0) or 0)
                        
                        # Only consider running if there is active contracts position or locked margin
                        if abs(active_pos) > 1e-6 or locked_margin > 0:
                            side = "LONG" if active_pos > 0 else "SHORT"
                            entry_price = float(p.get("avg_price", 0) or 0)
                            mark_price = float(p.get("mark_price", 0) or entry_price)
                            qty = abs(active_pos)
                            lev = int(float(p.get("leverage", 5) or 5))

                            # Calculate Unrealized PnL
                            if side == "LONG":
                                pnl_usd = (mark_price - entry_price) * qty
                            else:
                                pnl_usd = (entry_price - mark_price) * qty

                            margin_inr = locked_margin if locked_margin > 0 else round((entry_price * qty * rate) / max(1, lev), 2)
                            pnl_inr = round(pnl_usd * rate, 2)
                            pnl_pct = round((pnl_inr / max(1.0, margin_inr)) * 100.0, 2)

                            normalized = {
                                "id": p.get("id"),
                                "symbol": p.get("pair"),
                                "pair": p.get("pair"),
                                "side": side,
                                "active_pos": active_pos,
                                "quantity": qty,
                                "entry_price": entry_price,
                                "avg_price": entry_price,
                                "mark_price": mark_price,
                                "leverage": lev,
                                "margin": margin_inr,
                                "margin_inr": margin_inr,
                                "margin_currency": p.get("margin_currency_short_name", "INR"),
                                "unrealized_pnl": pnl_inr,
                                "unrealized_pnl_pct": pnl_pct,
                                "pnl": pnl_inr,
                                "pnl_pct": pnl_pct,
                                "liquidation_price": float(p.get("liquidation_price", 0) or 0),
                                "take_profit": float(p.get("take_profit_trigger", 0) or 0) if p.get("take_profit_trigger") else None,
                                "stop_loss": float(p.get("stop_loss_trigger", 0) or 0) if p.get("stop_loss_trigger") else None,
                                "is_live": True,
                                "mode": "LIVE"
                            }
                            active_positions.append(normalized)
                    return active_positions
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching positions: {e}")
            return []

    async def get_futures_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch historical live futures trade executions directly from CoinDCX."""
        if not self.api_key or not self.secret_key:
            return []

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/trades"
        body = {
            "timestamp": int(time.time() * 1000),
            "limit": limit
        }
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not isinstance(data, list):
                        return []
                    rate = await self.get_usdt_inr_rate()
                    normalized_trades = []
                    for t in data:
                        price = float(t.get("price", 0) or 0)
                        qty = float(t.get("quantity", 0) or 0)
                        raw_side = str(t.get("side", "BUY")).upper()
                        side = "LONG" if "BUY" in raw_side else "SHORT"
                        fee = float(t.get("fee_amount", 0) or 0)
                        ts = float(t.get("timestamp", 0) or time.time() * 1000) / 1000.0
                        notional_usd = price * qty
                        notional_inr = notional_usd * rate
                        normalized_trades.append({
                            "id": t.get("fill_id") or t.get("order_id"),
                            "symbol": t.get("pair"),
                            "pair": t.get("pair"),
                            "side": side,
                            "raw_side": raw_side,
                            "quantity": qty,
                            "price": price,
                            "entry_price": price,
                            "exit_price": price,
                            "notional_usd": round(notional_usd, 2),
                            "notional_inr": round(notional_inr, 2),
                            "fee": fee,
                            "margin_currency": t.get("margin_currency_short_name", "INR"),
                            "close_time": ts,
                            "reason": "LIVE_EXECUTION",
                            "is_live": True,
                            "mode": "LIVE"
                        })
                    return normalized_trades
                return []
        except Exception as e:
            print(f"[CoinDCX] Error fetching trades: {e}")
            return []

    async def create_futures_order(
        self,
        pair: str,
        side: str,  # 'buy' or 'sell'
        order_type: str = "market",  # 'market' or 'limit'
        quantity: float = 0.0,
        price: Optional[float] = None,
        leverage: int = 5,
        margin_currency: str = "INR"
    ) -> Dict[str, Any]:
        """Backward compatible order submission method."""
        return await self.create_futures_order_with_confirmation(
            pair=pair,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            leverage=leverage,
            margin_currency=margin_currency
        )

    async def create_futures_order_with_confirmation(
        self,
        pair: str,
        side: str,
        order_type: str = "market",
        quantity: float = 0.0,
        price: Optional[float] = None,
        leverage: int = 5,
        margin_currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Create a real INR-margined futures order on CoinDCX and parse the full confirmation.
        Returns status, order ID, human-readable success guide or error diagnostic.
        """
        if not self.api_key or not self.secret_key:
            return {
                "success": False,
                "status": "REJECTED_LOCAL",
                "error": "API Key and Secret Key required for live execution.",
                "guide": "Configure CoinDCX API credentials in Settings before submitting live orders."
            }

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/orders/create"
        clean_order_type = "market" if "market" in order_type.lower() else "limit"

        body = {
            "side": side.lower(),
            "order_type": clean_order_type,
            "pair": pair,
            "total_quantity": quantity,
            "leverage": leverage,
            "margin_currency_short_name": margin_currency.upper(),
            "position_margin_type": "ISOLATED",
            "timestamp": int(time.time() * 1000)
        }
        if clean_order_type == "limit" and price:
            body["price"] = price
            body["price_per_unit"] = price

        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                status_code = resp.status
                text = await resp.text()

                try:
                    data = json.loads(text)
                except Exception:
                    data = {"raw_text": text}

                # Case 1: CoinDCX returns a list of created orders
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    order_id = first.get("id") or first.get("order_id") or "live_order"
                    order_status = first.get("status") or "submitted"
                    return {
                        "success": True,
                        "order_id": order_id,
                        "status": order_status,
                        "pair": pair,
                        "side": side.upper(),
                        "quantity": quantity,
                        "leverage": leverage,
                        "margin_currency": margin_currency,
                        "message": f"✓ Live Order Confirmed by CoinDCX: {side.upper()} {quantity} {pair} (ID: {order_id}, Status: {order_status})",
                        "raw_response": data
                    }

                # Case 2: CoinDCX returns single dict order object
                if isinstance(data, dict) and (data.get("id") or data.get("order_id")):
                    order_id = data.get("id") or data.get("order_id")
                    order_status = data.get("status") or "submitted"
                    return {
                        "success": True,
                        "order_id": order_id,
                        "status": order_status,
                        "pair": pair,
                        "side": side.upper(),
                        "quantity": quantity,
                        "leverage": leverage,
                        "margin_currency": margin_currency,
                        "message": f"✓ Live Order Confirmed by CoinDCX: {side.upper()} {quantity} {pair} (ID: {order_id}, Status: {order_status})",
                        "raw_response": data
                    }

                # Case 3: CoinDCX returned an error response
                err_msg = ""
                if isinstance(data, dict):
                    err_msg = data.get("message") or data.get("error") or data.get("description") or text
                else:
                    err_msg = text

                guide = "Order rejected by CoinDCX."
                lower_err = err_msg.lower()
                if "insufficient" in lower_err or "balance" in lower_err or "margin" in lower_err:
                    guide = "Insufficient available INR margin in your CoinDCX wallet. Deposit or free up INR to place this trade."
                elif "quantity" in lower_err or "step" in lower_err or "lot" in lower_err:
                    guide = "Order quantity does not conform to CoinDCX minimum lot size or step precision."
                elif "price" in lower_err:
                    guide = "Order price deviates outside the acceptable futures price band."
                elif "signature" in lower_err or "auth" in lower_err:
                    guide = "Authentication signature mismatch. Ensure API Key and Secret are valid."

                return {
                    "success": False,
                    "status": "REJECTED_BY_EXCHANGE",
                    "status_code": status_code,
                    "error": err_msg,
                    "guide": guide,
                    "message": f"❌ CoinDCX Order Rejected: {err_msg}",
                    "raw_response": data
                }

        except Exception as e:
            return {
                "success": False,
                "status": "NETWORK_EXCEPTION",
                "error": str(e),
                "guide": "Failed to communicate with CoinDCX API server. Check network connection.",
                "message": f"❌ Network Error submitting order: {e}"
            }

    async def close_futures_position_with_confirmation(
        self,
        pair: str,
        side: str,  # current position side 'LONG' or 'SHORT'
        quantity: float,
        margin_currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Close an existing live position with full confirmation by executing
        an opposing market exit order on CoinDCX.
        """
        exit_side = "sell" if side.upper() == "LONG" else "buy"
        res = await self.create_futures_order_with_confirmation(
            pair=pair,
            side=exit_side,
            order_type="market",
            quantity=quantity,
            leverage=1,
            margin_currency=margin_currency
        )
        if res.get("success"):
            res["message"] = f"✓ Live Position Closed on CoinDCX: {pair} {side.upper()} exit executed ({res.get('status')})"
        return res

    async def cancel_futures_order_with_confirmation(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open futures order on CoinDCX."""
        if not self.api_key or not self.secret_key:
            return {"success": False, "error": "API credentials missing."}

        session = await self.get_session()
        url = f"{self.API_BASE_URL}/exchange/v1/derivatives/futures/orders/cancel"
        body = {
            "id": order_id,
            "timestamp": int(time.time() * 1000)
        }
        body_json = json.dumps(body, separators=(',', ':'))
        signature = self._generate_signature(body_json)

        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature
        }
        try:
            async with session.post(url, data=body_json, headers=headers) as resp:
                data = await resp.json()
                return {"success": resp.status == 200, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

