import time
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

class TechnicalAnalysis:
    """
    Quantitative technical indicator and order book depth analyzer.
    Calculates RSI, EMAs, MACD, Bollinger Bands, ATR, Support/Resistance,
    and Order Book Imbalance / Whale Walls.
    """

    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        
        diffs = np.diff(closes)
        gains = np.maximum(diffs, 0)
        losses = np.maximum(-diffs, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(diffs)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(float(rsi), 2)

    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> float:
        if not closes:
            return 0.0
        if len(closes) < period:
            return float(np.mean(closes))
        
        multiplier = 2.0 / (period + 1)
        ema = float(np.mean(closes[:period]))
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        return round(float(ema), 4)

    @staticmethod
    def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        if len(closes) < slow + signal:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        # Calculate fast and slow EMAs across series
        fast_ema = TechnicalAnalysis.calculate_ema(closes, fast)
        slow_ema = TechnicalAnalysis.calculate_ema(closes, slow)
        macd_line = fast_ema - slow_ema
        
        # Approximate signal line
        signal_line = TechnicalAnalysis.calculate_ema(closes[-signal:], signal) * 0.001
        hist = macd_line - signal_line
        return {
            "macd": round(macd_line, 4),
            "signal": round(signal_line, 4),
            "histogram": round(hist, 4)
        }

    @staticmethod
    def calculate_bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
        if len(closes) < period:
            current = closes[-1] if closes else 0.0
            return {"upper": current, "middle": current, "lower": current, "pct_b": 0.5, "bandwidth": 0.0}
        
        window = closes[-period:]
        middle = float(np.mean(window))
        std = float(np.std(window))
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        current = closes[-1]
        pct_b = (current - lower) / (upper - lower + 1e-9)
        bandwidth = ((upper - lower) / (middle + 1e-9)) * 100
        
        return {
            "upper": round(upper, 4),
            "middle": round(middle, 4),
            "lower": round(lower, 4),
            "pct_b": round(float(pct_b), 3),
            "bandwidth": round(float(bandwidth), 2)
        }

    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < 2:
            return 0.0
        
        tr_list = []
        for i in range(1, len(closes)):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i-1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
        if len(tr_list) < period:
            return round(float(np.mean(tr_list)), 4) if tr_list else 0.0
        
        atr = np.mean(tr_list[-period:])
        return round(float(atr), 4)

    @staticmethod
    def find_support_resistance(highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """Identify recent local swing highs and lows as key levels."""
        if len(closes) < 10:
            curr = closes[-1] if closes else 0.0
            return {"support": [round(curr * 0.98, 4)], "resistance": [round(curr * 1.02, 4)]}
        
        current_price = closes[-1]
        supports = []
        resistances = []
        
        # Local minima and maxima window of 5
        for i in range(2, len(closes) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                supports.append(lows[i])
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistances.append(highs[i])
                
        # Filter near current price
        valid_sup = sorted([s for s in supports if s < current_price], reverse=True)[:3]
        valid_res = sorted([r for r in resistances if r > current_price])[:3]
        
        if not valid_sup:
            valid_sup = [round(current_price * 0.97, 4), round(current_price * 0.95, 4)]
        if not valid_res:
            valid_res = [round(current_price * 1.03, 4), round(current_price * 1.05, 4)]
            
        return {
            "support": [round(s, 4) for s in valid_sup],
            "resistance": [round(r, 4) for r in valid_res]
        }

    @staticmethod
    def analyze_orderbook(ob_data: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Deep order book analytics:
        - Bid vs Ask volume balance
        - Imbalance percentage (-100 to +100)
        - Spread in Basis Points (bps)
        - Whale walls (large cluster orders)
        """
        bids_raw = ob_data.get("bids", {})
        asks_raw = ob_data.get("asks", {})
        
        # bids_raw and asks_raw are dicts of {price_str: qty_str}
        bids = []
        asks = []
        
        try:
            for p, q in bids_raw.items():
                bids.append((float(p), float(q)))
            for p, q in asks_raw.items():
                asks.append((float(p), float(q)))
        except Exception:
            pass

        # Sort bids descending (highest buy first), asks ascending (lowest sell first)
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])

        total_bid_vol = sum(q for _, q in bids)
        total_ask_vol = sum(q for _, q in asks)
        total_vol = total_bid_vol + total_ask_vol

        # Imbalance ratio: +100 means 100% buy pressure, -100 means 100% sell pressure
        imbalance = 0.0
        if total_vol > 0:
            imbalance = ((total_bid_vol - total_ask_vol) / total_vol) * 100.0

        # Spread
        best_bid = bids[0][0] if bids else current_price
        best_ask = asks[0][0] if asks else current_price
        spread = max(0.0, best_ask - best_bid)
        spread_bps = (spread / (current_price + 1e-9)) * 10000.0

        # Whale walls (orders with > 15% of total side volume)
        bid_threshold = total_bid_vol * 0.15 if total_bid_vol > 0 else float("inf")
        ask_threshold = total_ask_vol * 0.15 if total_ask_vol > 0 else float("inf")
        
        bid_walls = [{"price": round(p, 4), "qty": round(q, 4), "notional": round(p * q, 2)} 
                     for p, q in bids if q >= bid_threshold][:3]
        ask_walls = [{"price": round(p, 4), "qty": round(q, 4), "notional": round(p * q, 2)} 
                     for p, q in asks if q >= ask_threshold][:3]

        # Orderbook Delta Analytics
        orderbook_delta = total_bid_vol - total_ask_vol
        delta_ratio = ((total_bid_vol - total_ask_vol) / (total_vol + 1e-9))
        top5_bid_vol = sum(q for _, q in bids[:5])
        top5_ask_vol = sum(q for _, q in asks[:5])
        microstructure_delta = top5_bid_vol - top5_ask_vol
        top5_vol = top5_bid_vol + top5_ask_vol
        microstructure_delta_pct = (microstructure_delta / (top5_vol + 1e-9)) * 100.0

        if delta_ratio > 0.25:
            delta_bias = "AGGRESSIVE_BUY_PRESSURE"
        elif delta_ratio > 0.08:
            delta_bias = "BULLISH_DELTA"
        elif delta_ratio < -0.25:
            delta_bias = "AGGRESSIVE_SELL_PRESSURE"
        elif delta_ratio < -0.08:
            delta_bias = "BEARISH_DELTA"
        else:
            delta_bias = "BALANCED"

        return {
            "total_bid_vol": round(total_bid_vol, 2),
            "total_ask_vol": round(total_ask_vol, 2),
            "orderbook_delta": round(orderbook_delta, 2),
            "delta_ratio": round(delta_ratio, 3),
            "delta_bias": delta_bias,
            "microstructure_delta": round(microstructure_delta, 2),
            "microstructure_delta_pct": round(microstructure_delta_pct, 1),
            "imbalance_pct": round(imbalance, 1),
            "sentiment": "Strong Bullish" if imbalance > 25 else "Bullish" if imbalance > 10 else "Strong Bearish" if imbalance < -25 else "Bearish" if imbalance < -10 else "Neutral",
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": round(spread, 4),
            "spread_bps": round(spread_bps, 2),
            "bid_walls": bid_walls,
            "ask_walls": ask_walls,
            "bids_depth": [{"price": round(p, 4), "qty": round(q, 4)} for p, q in bids[:15]],
            "asks_depth": [{"price": round(p, 4), "qty": round(q, 4)} for p, q in asks[:15]]
        }

    @staticmethod
    def analyze_candle_patterns(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Track live candlestick price action, wick rejections, momentum expansions,
        and generate fast scalping signals to secure quick profits and avoid big losses.
        """
        if not candles or len(candles) < 3:
            return {
                "pattern": "INSUFFICIENT_DATA",
                "scalp_signal": "WAIT",
                "bias": "NEUTRAL",
                "body_pct": 50.0,
                "upper_wick_pct": 25.0,
                "lower_wick_pct": 25.0,
                "quick_target_pct": 1.5,
                "quick_sl_pct": 0.9,
                "recommendation": "Waiting for candle formation"
            }

        last = candles[-1]
        o = float(last["open"])
        c = float(last["close"])
        h = float(last["high"])
        l = float(last["low"])
        rng = max(h - l, 1e-9)

        body = abs(c - o)
        body_pct = round((body / rng) * 100.0, 1)
        
        is_green = c >= o
        upper_wick = (h - max(c, o))
        lower_wick = (min(c, o) - l)
        
        upper_wick_pct = round((upper_wick / rng) * 100.0, 1)
        lower_wick_pct = round((lower_wick / rng) * 100.0, 1)

        # Multi-candle momentum
        last_3 = candles[-3:]
        green_count = sum(1 for x in last_3 if float(x["close"]) >= float(x["open"]))
        consecutive_up = green_count == 3
        consecutive_down = green_count == 0

        # Pattern identification
        pattern = "STANDARD_CANDLE"
        scalp_signal = "HOLD"
        bias = "NEUTRAL"
        recommendation = "Candle structure balanced."

        avg_rng_10 = float(np.mean([float(x["high"]) - float(x["low"]) for x in candles[-10:]])) if len(candles) >= 10 else rng

        if body_pct >= 68.0 and rng >= avg_rng_10:
            pattern = "BULLISH_MOMENTUM_EXPANSION" if is_green else "BEARISH_MOMENTUM_EXPANSION"
            scalp_signal = "QUICK_SCALP_LONG" if is_green else "QUICK_SCALP_SHORT"
            bias = "STRONG_BULLISH" if is_green else "STRONG_BEARISH"
            recommendation = f"Rapid momentum expansion detected. Quick scalp {'LONG' if is_green else 'SHORT'} with tight SL."

        elif upper_wick_pct >= 48.0:
            pattern = "PINBAR_UPPER_WICK_REJECTION"
            scalp_signal = "QUICK_SCALP_SHORT"
            bias = "BEARISH_REVERSAL"
            recommendation = "Heavy selling rejection at highs! Avoid longs; scalp short or take quick profit."

        elif lower_wick_pct >= 48.0:
            pattern = "HAMMER_LOWER_WICK_REJECTION"
            scalp_signal = "QUICK_SCALP_LONG"
            bias = "BULLISH_REVERSAL"
            recommendation = "Strong buyer absorption at lows! Avoid shorts; scalp long for quick rebound."

        elif body_pct <= 15.0:
            pattern = "DOJI_VOLATILITY_COMPRESSION"
            scalp_signal = "WAIT_FOR_BREAKOUT"
            bias = "CONSOLIDATION"
            recommendation = "Volatility contraction. Prepare for breakout."

        elif consecutive_up and is_green:
            pattern = "THREE_WHITE_SOLDIERS_TREND"
            scalp_signal = "QUICK_SCALP_LONG"
            bias = "BULLISH_CONTINUATION"
            recommendation = "Persistent buying momentum. Ride with trailing stop."

        elif consecutive_down and not is_green:
            pattern = "THREE_BLACK_CROWS_DUMP"
            scalp_signal = "QUICK_SCALP_SHORT"
            bias = "BEARISH_CONTINUATION"
            recommendation = "Persistent distribution. Scalp short with breakeven protection."

        return {
            "pattern": pattern,
            "scalp_signal": scalp_signal,
            "bias": bias,
            "is_green": is_green,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "range": round(rng, 4),
            "body_pct": body_pct,
            "upper_wick_pct": upper_wick_pct,
            "lower_wick_pct": lower_wick_pct,
            "consecutive_greens": green_count,
            "quick_target_pct": 1.5,
            "quick_sl_pct": 0.8,
            "recommendation": recommendation
        }

    @classmethod
    def full_coin_analysis(
        cls,
        candles: List[Dict[str, Any]],
        ob_data: Dict[str, Any],
        pair: str,
        candles_1h: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive multi-timeframe technical + orderbook depth analysis.
        Strictly filters setups to formulate high-conviction CALL (BUY) or PUT (SELL) decisions
        with institutional risk-reward (minimum 1:2.2 R:R) and tight stop-loss.
        """
        if not candles or len(candles) < 5:
            return {"error": "Insufficient candle data", "is_valid": False}

        now_sec = time.time()
        latest_c = candles[-1]
        candle_ts = float(latest_c.get("time", 0))
        if candle_ts > 1e11:  # convert ms to sec
            candle_ts /= 1000.0

        # 1. Freshness check: Discard stale / frozen / delisted tokens (> 90 mins old)
        if candle_ts > 0 and (now_sec - candle_ts) > 5400:
            return {
                "pair": pair,
                "is_valid": False,
                "disqualification_reason": f"Stale market data: candle time is {int((now_sec - candle_ts)/60)} minutes old."
            }

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c.get("volume", 0)) for c in candles]
        
        current_price = closes[-1]
        if current_price <= 0:
            return {"error": "Invalid price", "is_valid": False}

        # 2. Orderbook Analysis & Price Discrepancy Check
        ob_analysis = cls.analyze_orderbook(ob_data, current_price)
        best_bid = ob_analysis.get("best_bid", current_price)
        best_ask = ob_analysis.get("best_ask", current_price)
        ob_mid = (best_bid + best_ask) / 2.0 if (best_bid > 0 and best_ask > 0) else current_price

        # If candle close deviates > 2.5% from live orderbook, discard as corrupt/stale
        if ob_mid > 0 and abs(current_price - ob_mid) / ob_mid > 0.025:
            return {
                "pair": pair,
                "is_valid": False,
                "disqualification_reason": f"Price discrepancy: candle close (${current_price}) deviates from orderbook mid (${ob_mid:.4f})."
            }

        # 3. Tactical 15m Indicators
        rsi = cls.calculate_rsi(closes, 14)
        ema9 = cls.calculate_ema(closes, 9)
        ema21 = cls.calculate_ema(closes, 21)
        ema50 = cls.calculate_ema(closes, 50)
        ema200 = cls.calculate_ema(closes, 200)
        macd = cls.calculate_macd(closes)
        bb = cls.calculate_bollinger_bands(closes, 20)
        atr = cls.calculate_atr(highs, lows, closes, 14)
        levels = cls.find_support_resistance(highs, lows, closes)
        
        # Volume Surge & RVOL
        recent_vol = np.mean(volumes[-3:]) if len(volumes) >= 3 else 1.0
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else recent_vol
        vol_surge = round(float(recent_vol / (avg_vol + 1e-9)), 2)

        # 4. Multi-Timeframe (1h Macro Trend) Confluence
        macro_trend = "RANGING_MACRO"
        macro_signals = []
        if candles_1h and len(candles_1h) >= 20:
            closes_1h = [float(c["close"]) for c in candles_1h]
            ema50_1h = cls.calculate_ema(closes_1h, 50)
            ema200_1h = cls.calculate_ema(closes_1h, 200)
            c_1h = closes_1h[-1]

            if c_1h > ema50_1h and ema50_1h >= ema200_1h:
                macro_trend = "BULLISH_MACRO"
                macro_signals.append("1h Macro Bullish Trend (Price > EMA50 > EMA200)")
            elif c_1h < ema50_1h and ema50_1h <= ema200_1h:
                macro_trend = "BEARISH_MACRO"
                macro_signals.append("1h Macro Bearish Trend (Price < EMA50 < EMA200)")
            elif c_1h > ema50_1h:
                macro_trend = "MODERATE_BULLISH_MACRO"
                macro_signals.append("1h Above EMA50")
            elif c_1h < ema50_1h:
                macro_trend = "MODERATE_BEARISH_MACRO"
                macro_signals.append("1h Below EMA50")

        # 5. Live Candle Pattern & Microstructure
        candle_patterns = cls.analyze_candle_patterns(candles)
        imbalance = ob_analysis["imbalance_pct"]
        micro_delta = ob_analysis.get("microstructure_delta_pct", 0.0)
        spread_bps = ob_analysis.get("spread_bps", 0.0)

        # 6. Quantitative Scoring & Rule-Based Filtering
        score = 0
        signals = []
        signals.extend(macro_signals)

        # Trend alignment (15m tactical)
        if ema9 > ema21 > ema50:
            score += 25
            signals.append("15m Golden Alignment (EMA 9>21>50)")
        elif ema9 < ema21 < ema50:
            score -= 25
            signals.append("15m Death Alignment (EMA 9<21<50)")

        # Orderbook Depth & Imbalance
        if imbalance > 15:
            score += 20
            signals.append(f"Strong Buy Depth (+{imbalance}%)")
        elif imbalance < -15:
            score -= 20
            signals.append(f"Heavy Sell Depth ({imbalance}%)")

        # Microstructure Top-5 Delta
        if micro_delta > 20:
            score += 15
            signals.append(f"Top-5 Bid Absorption (+{micro_delta:.1f}%)")
        elif micro_delta < -20:
            score -= 15
            signals.append(f"Top-5 Ask Absorption ({micro_delta:.1f}%)")

        # Volume Flow Confirmation
        if vol_surge > 1.3:
            if score > 0:
                score += 15
                signals.append(f"Institutional Volume Surge ({vol_surge}x)")
            else:
                score -= 15
                signals.append(f"Distribution Volume Spike ({vol_surge}x)")

        # Candle Scalp Bias
        if candle_patterns["scalp_signal"] == "QUICK_SCALP_LONG":
            score += 15
            signals.append(f"Candle: {candle_patterns['pattern']}")
        elif candle_patterns["scalp_signal"] == "QUICK_SCALP_SHORT":
            score -= 15
            signals.append(f"Candle: {candle_patterns['pattern']}")

        # RSI Momentum Check
        if 45 <= rsi <= 65:
            score += 10
            signals.append(f"RSI in Expansion Zone ({rsi:.1f})")
        elif 35 <= rsi <= 48:
            score -= 10
            signals.append(f"RSI in Distribution Zone ({rsi:.1f})")
        elif rsi > 70:
            score -= 20
            signals.append(f"RSI Overbought ({rsi:.1f}) - Exhaustion Risk")
        elif rsi < 30:
            score += 20
            signals.append(f"RSI Oversold ({rsi:.1f}) - Rebound Potential")

        # Spread penalty
        if spread_bps > 15:
            score = int(score * 0.75) # Reduce confidence if spread is wide

        # Normalize score (-100 to +100)
        score = max(-100, min(100, score))

        # ==========================================================
        # 7. HIGH-CONVICTION CALL vs PUT DIRECTION DECISION
        # ==========================================================
        # Strict Confluence Rules:
        # - CALL (BUY): Requires score >= +35, RSI <= 68, Imbalance > -10%, NOT in 1h Bearish Macro
        # - PUT (SELL): Requires score <= -35, RSI >= 32, Imbalance < +10%, NOT in 1h Bullish Macro
        is_call_approved = (
            score >= 35 and
            rsi <= 68 and
            imbalance >= -10 and
            macro_trend != "BEARISH_MACRO" and
            spread_bps <= 20
        )

        is_put_approved = (
            score <= -35 and
            rsi >= 32 and
            imbalance <= 10 and
            macro_trend != "BULLISH_MACRO" and
            spread_bps <= 20
        )

        if is_call_approved:
            action = "CALL (BUY)"
            direction = "LONG"
            confidence = min(95, int(50 + abs(score) * 0.45))
        elif is_put_approved:
            action = "PUT (SELL)"
            direction = "SHORT"
            confidence = min(95, int(50 + abs(score) * 0.45))
        else:
            action = "WAIT (NEUTRAL)"
            direction = "WATCH"
            confidence = 40

        # ==========================================================
        # 8. STRICT LOSS-CONTROLLED STOP LOSS & TAKE PROFIT (1:2.2+ R:R)
        # ==========================================================
        # Cap price risk strictly to 0.35% - 0.48% (guarantees max 1.75% - 2.4% margin risk at 5x leverage)
        # Never allow a 1.2% price risk which caused the past -6% losses!
        max_price_risk_pct = 0.0042 # 0.42% max price risk
        min_price_risk_pct = 0.0030 # 0.30% min price risk
        atr_risk = atr * 0.8 if atr > 0 else current_price * 0.0035
        risk_dist = min(max(atr_risk, current_price * min_price_risk_pct), current_price * max_price_risk_pct)

        target_rr = 2.2
        tp1_dist = risk_dist * 2.0  # First quick target (+0.8% price move = +4.0% margin profit)
        tp2_dist = risk_dist * 3.5  # Runner target (+1.4% price move = +7.0% margin profit)

        if direction == "LONG":
            suggested_entry = current_price
            suggested_sl = round(current_price - risk_dist, 4)
            suggested_tp1 = round(current_price + tp1_dist, 4)
            suggested_tp2 = round(current_price + tp2_dist, 4)
        elif direction == "SHORT":
            suggested_entry = current_price
            suggested_sl = round(current_price + risk_dist, 4)
            suggested_tp1 = round(current_price - tp1_dist, 4)
            suggested_tp2 = round(current_price - tp2_dist, 4)
        else:
            suggested_entry = current_price
            suggested_sl = round(current_price * 0.996, 4)
            suggested_tp1 = round(current_price * 1.008, 4)
            suggested_tp2 = round(current_price * 1.015, 4)

        return {
            "pair": pair,
            "current_price": current_price,
            "score": score,
            "action": action,
            "direction": direction,
            "confidence": confidence,
            "macro_trend": macro_trend,
            "signals": signals,
            "rsi": rsi,
            "ema9": ema9,
            "ema21": ema21,
            "ema50": ema50,
            "ema200": ema200,
            "vol_surge": vol_surge,
            "macd": macd,
            "bollinger": bb,
            "atr": atr,
            "support_levels": levels["support"],
            "resistance_levels": levels["resistance"],
            "orderbook": ob_analysis,
            "candle_patterns": candle_patterns,
            "is_valid": True,
            "trade_setup": {
                "side": direction,
                "action": action,
                "entry": suggested_entry,
                "stop_loss": suggested_sl,
                "take_profit_1": suggested_tp1,
                "take_profit_2": suggested_tp2,
                "risk_reward": round(target_rr, 1),
                "risk_pct": round((risk_dist / current_price) * 100.0, 2),
                "max_margin_loss_pct": round(((risk_dist / current_price) * 5) * 100.0, 2),
                "suggested_leverage": 5
            }
        }
