import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from .coindcx_client import CoinDCXClient
from .technical_analysis import TechnicalAnalysis
from .scanner import MarketScanner
from .llm_engine import LLMEngine
from .paper_engine import PaperTradingEngine
from .self_learning import SelfLearningStrategyEngine
from .telegram_notifier import TelegramNotifier

class AutoTradingAgent:
    """
    Autonomous AI Futures Auto-Trader with Self-Correcting Mistake Memory & Adaptive Strategies.
    - Scans markets continuously for high-confluence setups.
    - Consults Local LLM for trade execution plans.
    - Uses SelfLearningStrategyEngine to avoid repeating mistakes & improve strategies.
    - Uses Dynamic Compounding Balance Sizing to scale positions on winning streaks.
    - Captures full API confirmations from CoinDCX on order placement and exits.
    - Broadcasts Sure Calls, Order Executions, TP Hits & SL protections to Telegram.
    """
    MEMORY_FILE = os.path.join("data", "ai_memory.json")

    def __init__(
        self,
        client: CoinDCXClient,
        scanner: MarketScanner,
        llm: LLMEngine,
        paper: PaperTradingEngine,
        telegram: Optional[TelegramNotifier] = None
    ):
        self.client = client
        self.scanner = scanner
        self.llm = llm
        self.paper = paper
        self.telegram = telegram
        self.learning_engine = SelfLearningStrategyEngine()

        self.is_running: bool = False
        self.task: Optional[asyncio.Task] = None
        self.symbol_cooldowns: Dict[str, float] = {}  # symbol -> cooldown expiry timestamp

        # Settings
        self.config: Dict[str, Any] = {
            "enabled": False,
            "min_score": 35,             # Minimum quant composite score to enter (0-100)
            "max_open_positions": 3,     # Max concurrent positions
            "leverage": 5,               # Default leverage
            "position_size_inr": 25000.0,# Margin allocated per trade in INR (default ₹25,000)
            "position_size_usd": 250.0,  # Fallback margin in USD
            "risk_pct_per_trade": 5.0,   # Max 5% of balance per trade to cap risk
            "scan_interval_sec": 20,     # Time between autonomous scans
            "risk_reward_min": 1.8,      # Minimum target R:R ratio
            "live_trading_enabled": False# Real CoinDCX INR Wallet execution
        }

        # Adaptive Learning & Mistake Memory
        self.memory: Dict[str, Any] = {
            "total_mistakes_avoided": 0,
            "learned_lessons": [],       # List of negative rules learned from bad trades
            "profitable_patterns": [],   # Patterns that repeatedly won
            "agent_activity_logs": [],   # Action log history for UI
            "last_scan_time": 0.0
        }
        self.load_memory()

    def load_memory(self):
        """Load learned memory and config from disk."""
        if os.path.exists(self.MEMORY_FILE):
            try:
                with open(self.MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memory.update(data.get("memory", {}))
                    self.config.update(data.get("config", {}))
            except Exception as e:
                print(f"[AutoTrader] Error loading memory: {e}")
        else:
            # Seed with baseline institutional risk rules
            self.memory["learned_lessons"] = [
                {
                    "id": "rule_1",
                    "condition": "RSI > 70 Long Entry",
                    "reason": "Overbought exhaustion. High probability of pullback.",
                    "action": "REJECT_LONG",
                    "learned_from": "Initial Market Prior"
                },
                {
                    "id": "rule_2",
                    "condition": "RSI < 28 Short Entry",
                    "reason": "Oversold bounce risk. Sellers exhausted.",
                    "action": "REJECT_SHORT",
                    "learned_from": "Initial Market Prior"
                },
                {
                    "id": "rule_3",
                    "condition": "Order Book Imbalance < -20% on Long",
                    "reason": "Heavy sell walls overhead; buyers lacked orderbook absorption.",
                    "action": "REJECT_LONG",
                    "learned_from": "Order Book Microstructure Analysis"
                }
            ]
            self.save_memory()

    def save_memory(self):
        """Persist learned memory and agent config to disk."""
        os.makedirs(os.path.dirname(self.MEMORY_FILE), exist_ok=True)
        try:
            with open(self.MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"config": self.config, "memory": self.memory}, f, indent=2)
        except Exception as e:
            print(f"[AutoTrader] Error saving memory: {e}")

    def log_action(self, action_type: str, message: str, meta: Optional[Dict[str, Any]] = None):
        """Append to live agent activity log."""
        log_entry = {
            "timestamp": time.time(),
            "time_str": time.strftime("%H:%M:%S"),
            "type": action_type, # 'SCAN', 'ENTRY', 'REJECT', 'LEARN', 'CLOSE'
            "message": message,
            "meta": meta or {}
        }
        self.memory["agent_activity_logs"].insert(0, log_entry)
        # Keep last 100 logs
        self.memory["agent_activity_logs"] = self.memory["agent_activity_logs"][:100]
        self.save_memory()

    def evaluate_against_learned_mistakes(self, analysis: Dict[str, Any], direction: str) -> Tuple[bool, Optional[str]]:
        """
        Check current candidate against past mistakes.
        Returns (is_safe, rejection_reason).
        """
        rsi = analysis.get("rsi", 50.0)
        ob = analysis.get("orderbook", {})
        imbalance = ob.get("imbalance_pct", 0.0)
        pair = analysis.get("pair", "")

        for rule in self.memory.get("learned_lessons", []):
            action = rule.get("action", "")
            
            # Check Long Rejections
            if direction == "LONG" and action == "REJECT_LONG":
                if "RSI > 70" in rule.get("condition", "") and rsi > 68:
                    return False, f"Memory Rule ({rule['id']}): Incurred loss previously buying into RSI {rsi:.1f} exhaustion."
                if "Imbalance < -20%" in rule.get("condition", "") and imbalance < -18:
                    return False, f"Memory Rule ({rule['id']}): Heavy sell wall ({imbalance}%) previously triggered invalidation."

            # Check Short Rejections
            if direction == "SHORT" and action == "REJECT_SHORT":
                if "RSI < 28" in rule.get("condition", "") and rsi < 32:
                    return False, f"Memory Rule ({rule['id']}): Incurred loss previously shorting into oversold RSI {rsi:.1f} rebound."
                if "Imbalance > +20%" in rule.get("condition", "") and imbalance > 18:
                    return False, f"Memory Rule ({rule['id']}): Strong buy wall (+{imbalance}%) defended price against short."

            # Check specific symbol blacklists or lessons
            if rule.get("symbol") == pair and rule.get("side") == direction:
                cooldown_sec = rule.get("cooldown_sec", 600)
                if time.time() - rule.get("timestamp", 0) < cooldown_sec:
                    return False, f"Recent Mistake Cooldown: {rule.get('reason')}"

        return True, None

    async def conduct_post_trade_autopsy(self, closed_trade: Dict[str, Any]):
        """
        Self-Correction Engine:
        Analyzes closed trade. If it lost money, extracts the mistake pattern,
        synthesizes a new negative rule, and tightens the responsible strategy.
        If it made money, reinforces the pattern and expands profit capture!
        """
        pnl = closed_trade.get("realized_pnl", 0.0)
        symbol = closed_trade.get("symbol", "")
        side = closed_trade.get("side", "")
        reason = closed_trade.get("reason", "")
        duration = closed_trade.get("duration_sec", 0)

        if pnl < 0:
            # 1. Immediate 60-minute circuit breaker / cooldown on this symbol to prevent repeat losses!
            self.symbol_cooldowns[symbol] = time.time() + 3600
            
            # Mistake autopsy
            loss_pct = closed_trade.get("pnl_pct", 0.0)
            print(f"[AutoTrader Autopsy] Trade {symbol} ({side}) exited at a loss: ₹{abs(pnl):,.2f} ({loss_pct}%). Locked out for 60m.")

            lesson_desc = f"Loss on {symbol} {side} ({reason}). Stopped out after {duration}s."
            
            # Consult local LLM for smart autopsy summary if online
            try:
                autopsy_prompt = (
                    f"A futures trade on {symbol} ({side}) hit {reason} resulting in a loss of -₹{abs(pnl):,.2f}. "
                    f"In 1 crisp sentence, formulate a strict risk rule to avoid repeating this exact mistake in crypto futures."
                )
                ai_rule_text = await self.llm.generate(autopsy_prompt, max_tokens=60, temperature=0.3)
                if ai_rule_text and len(ai_rule_text.strip()) > 10:
                    lesson_desc = ai_rule_text.strip()
            except Exception as e:
                print(f"[AutoTrader] LLM autopsy error: {e}")

            # 2. Update legacy memory with 60-min lockout
            new_rule = {
                "id": f"lesson_{int(time.time())}",
                "symbol": symbol,
                "side": side,
                "timestamp": time.time(),
                "cooldown_sec": 3600, # 60 min cooldown on same pair & direction
                "condition": f"Failure on {symbol} {side} exit via {reason}",
                "reason": lesson_desc,
                "action": f"REJECT_{side}",
                "learned_from": f"Realized Loss of ₹{abs(pnl):,.2f}"
            }
            self.memory["learned_lessons"].insert(0, new_rule)
            self.memory["learned_lessons"] = self.memory["learned_lessons"][:30]

            # 3. Deep Self-Learning & Strategy Adaptation Engine
            await self.learning_engine.learn_from_mistake(closed_trade, lesson_desc)

            self.log_action("LEARN", f"Circuit Breaker: {symbol} on 60m cooldown. Lesson: {lesson_desc}", {"loss_inr": pnl, "symbol": symbol})
        else:
            # Positive reinforcement & strategy win rate expansion
            print(f"[AutoTrader Autopsy] Trade {symbol} ({side}) succeeded with profit +₹{pnl:,.2f}!")
            self.learning_engine.learn_from_win(closed_trade)
            self.log_action("CLOSE", f"Successfully closed {symbol} {side} with profit +₹{pnl:,.2f} (Pattern reinforced)", {"profit_inr": pnl})

        self.save_memory()

    async def scan_candle_and_decide(self, pair: str, interval: str = "1h") -> Dict[str, Any]:
        """
        LLM Candle Structure Scanner & Trade Formulator:
        Reads recent candles, calculates indicators, inspects order book walls,
        evaluates against Mistake Memory, and asks the local GPU LLM to decide
        the highest-profit action (BUY, SELL, or HOLD).
        """
        candles = await self.client.get_candles(pair, interval=interval, limit=40)
        ob = await self.client.get_orderbook(pair, depth=15)
        
        if not candles or len(candles) < 15:
            return {
                "pair": pair,
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"Insufficient candle data for {pair} to formulate setup.",
                "trade_setup": None
            }

        analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair)
        price = analysis.get("current_price", 0.0)
        rsi = analysis.get("rsi", 50.0)
        ob_analysis = analysis.get("orderbook", {})
        imbalance = ob_analysis.get("imbalance_pct", 0.0)
        ob_delta = ob_analysis.get("orderbook_delta", 0.0)
        delta_bias = ob_analysis.get("delta_bias", "BALANCED")
        micro_delta = ob_analysis.get("microstructure_delta_pct", 0.0)
        spread_bps = ob_analysis.get("spread_bps", 0.0)
        setup = analysis.get("trade_setup", {})
        quant_score = analysis.get("score", 0)

        candle_patterns = analysis.get("candle_patterns") or TechnicalAnalysis.analyze_candle_patterns(candles)

        # Summarize last 5 candles for LLM context
        last_5 = candles[-5:]
        candle_summary = []
        for i, c in enumerate(last_5):
            o = float(c["open"])
            cl = float(c["close"])
            h = float(c["high"])
            l = float(c["low"])
            dir_str = "BULLISH (Green)" if cl >= o else "BEARISH (Red)"
            candle_summary.append(f"T-{4-i}: Open {o}, High {h}, Low {l}, Close {cl} -> {dir_str}")
        candle_text = "\n".join(candle_summary)

        # Gathers active mistake memory
        active_lessons = self.memory.get("learned_lessons", [])[:4]
        lessons_text = "\n".join([f"- {l.get('condition')}: {l.get('reason')}" for l in active_lessons]) or "None yet recorded."

        # Prompt local GPU LLM with rich Orderbook Delta, Candlestick Formations & Quick Profit Scalping
        prompt = (
            f"You are an institutional crypto futures quantitative trader on CoinDCX.\n"
            f"TARGET PAIR: {pair}\n"
            f"CURRENT PRICE: ${price}\n"
            f"QUANT COMPOSITE SCORE: {quant_score}/100\n"
            f"CANDLE PATTERN: {candle_patterns.get('pattern')} (Body: {candle_patterns.get('body_pct')}%, Upper Wick: {candle_patterns.get('upper_wick_pct')}%, Lower Wick: {candle_patterns.get('lower_wick_pct')}%)\n"
            f"CANDLE SCALP BIAS: {candle_patterns.get('scalp_signal')} ({candle_patterns.get('recommendation')})\n"
            f"RSI (14): {rsi:.1f}\n"
            f"ORDERBOOK DELTA (Bids - Asks): {ob_delta:+.2f} ({delta_bias})\n"
            f"ORDERBOOK IMBALANCE: {imbalance:+.1f}%\n"
            f"TOP-5 MICROSTRUCTURE DELTA: {micro_delta:+.1f}% | SPREAD: {spread_bps:.1f} bps\n"
            f"RECENT 5 CANDLES:\n{candle_text}\n\n"
            f"MISTAKES & LESSONS TO AVOID (FROM PAST LOSSES):\n{lessons_text}\n\n"
            f"FOCUSED MISSION: Track live candle momentum and formulate a QUICK PROFIT scalp setup (+1.2% to +1.8% target) with tight invalidation (+0.8% breakeven lock) to bank fast profits and avoid big losses!\n"
            f"Provide your decision strictly in this format:\n"
            f"DECISION: [BUY / SELL / HOLD]\n"
            f"CONFIDENCE: [0-100]%\n"
            f"RECOMMENDED_LEVERAGE: [1-10]x\n"
            f"TRAILING_OFFSET_PCT: [0.6-1.0]%\n"
            f"ENTRY: [price]\n"
            f"STOP_LOSS: [price]\n"
            f"TAKE_PROFIT: [price]\n"
            f"CANDLE_ANALYSIS: [explain how latest candle wicks and momentum support this scalp]\n"
            f"MISTAKE_AVOIDED: [explain which past mistake is avoided]\n"
            f"REASONING: [concise institutional rationale]"
        )

        try:
            llm_reply = await self.llm.generate(prompt, max_tokens=300, temperature=0.2)
        except Exception as e:
            llm_reply = f"DECISION: {setup.get('side', 'HOLD')}\nCONFIDENCE: 75%\nCANDLE_ANALYSIS: {candle_patterns.get('pattern')}: {candle_patterns.get('recommendation')}\nREASONING: Quantitative technical rule formulation: Score {quant_score}/100 with {delta_bias} orderbook delta."

        # Parse decision
        decision = "HOLD"
        confidence = 60
        if "DECISION: BUY" in llm_reply or "DECISION: LONG" in llm_reply:
            decision = "BUY"
        elif "DECISION: SELL" in llm_reply or "DECISION: SHORT" in llm_reply:
            decision = "SELL"

        # Check mistake memory rules
        check_dir = "LONG" if decision == "BUY" else "SHORT" if decision == "SELL" else "HOLD"
        is_safe, rej = self.evaluate_against_learned_mistakes(analysis, check_dir)
        if not is_safe:
            self.memory["total_mistakes_avoided"] += 1
            self.save_memory()
            llm_reply += f"\n\n⚠️ OVERRIDE BY MISTAKE MEMORY: Reverting to HOLD because: {rej}"
            decision = "HOLD"

        return {
            "pair": pair,
            "decision": decision,
            "confidence": confidence,
            "price": price,
            "rsi": rsi,
            "imbalance": imbalance,
            "candle_patterns": candle_patterns,
            "trade_setup": setup,
            "reasoning": llm_reply,
            "is_safe": is_safe
        }

    async def execute_trade_decision(self, candidate: Dict[str, Any]):
        """Execute autonomous entry after verifying safety and risk."""
        pair = candidate.get("pair") or candidate.get("symbol")
        score = candidate.get("score", 0)
        setup = candidate.get("trade_setup", {})
        direction = setup.get("side", "WATCH")
        action = candidate.get("action", "")

        # 1. Strict Action & Direction validation: Only trade confirmed CALL (BUY) or PUT (SELL)
        if direction not in ["LONG", "SHORT"]:
            return
        if action not in ["CALL (BUY)", "PUT (SELL)"]:
            return

        # 2. Check Symbol Loss Cooldown (60 min lockout after any stopped-out trade)
        cooldown_until = self.symbol_cooldowns.get(pair, 0)
        if time.time() < cooldown_until:
            rem_min = max(1, int((cooldown_until - time.time()) / 60))
            self.log_action("COOLDOWN", f"Skipped entry on {pair}: under {rem_min}m risk cooldown from previous loss.")
            return

        # 3. Check current open positions count
        acc = self.paper.get_summary()
        active_positions = acc.get("positions", [])
        if len(active_positions) >= self.config["max_open_positions"]:
            self.log_action("REJECT", f"Max concurrent positions reached ({len(active_positions)}/{self.config['max_open_positions']})")
            return

        # Check if already positioned in this symbol
        if any(p["symbol"] == pair for p in active_positions):
            return

        # 4. Check Mistake Memory & Select Optimal Self-Improved Strategy
        is_safe, rejection_reason, chosen_strat = self.learning_engine.evaluate_candidate(candidate, direction)
        if not is_safe:
            self.memory["total_mistakes_avoided"] += 1
            self.log_action("AVOID_MISTAKE", f"Avoided entering {pair} {direction}: {rejection_reason}", {"pair": pair, "reason": rejection_reason})
            self.save_memory()
            return

        is_safe_mem, mem_rej = self.evaluate_against_learned_mistakes(candidate, direction)
        if not is_safe_mem:
            self.memory["total_mistakes_avoided"] += 1
            self.log_action("AVOID_MISTAKE", f"Avoided entering {pair} {direction}: {mem_rej}", {"pair": pair, "reason": mem_rej})
            self.save_memory()
            return

        strat_name = chosen_strat.get("name", "Adaptive Confluence")
        strat_id = chosen_strat.get("id", "strat_default")
        leverage = chosen_strat.get("leverage") or int(self.config.get("leverage", 5))
        trailing_offset = chosen_strat.get("trailing_sl_offset_pct") or 1.2

        # 5. Price & Stop-Loss sanity checks
        price = candidate.get("current_price", 0.0)
        if price <= 0:
            return

        sl = setup.get("stop_loss")
        tp = setup.get("take_profit_1")

        # Invalidation check: Stop loss must be on correct side of entry
        if sl is not None:
            if direction == "LONG" and price <= sl:
                return
            if direction == "SHORT" and price >= sl:
                return

        rr = setup.get("risk_reward", 2.0)
        if rr < self.config.get("risk_reward_min", 1.8):
            return

        # 6. Strictly Controlled Position Sizing in INR (Capped to max 5% of balance / max ₹35,000)
        rate = await self.client.get_usdt_inr_rate()
        is_live = bool(self.config.get("live_trading_enabled", False) and self.client.api_key and self.client.secret_key)

        if is_live:
            wallet = await self.client.get_inr_wallet_summary()
            avail_inr = wallet.get("inr_available", 0.0)
        else:
            avail_inr = self.paper.state["balance"]

        sizing_info = self.learning_engine.calculate_compound_position_size(
            available_balance_inr=avail_inr,
            risk_pct=float(self.config.get("risk_pct_per_trade", 5.0)),
            min_margin_inr=15000.0,
            max_margin_inr=35000.0
        )
        margin_alloc_inr = sizing_info["margin_inr"]
        
        # Notional in INR = margin_inr * leverage
        notional_inr = margin_alloc_inr * leverage
        notional_usd = notional_inr / rate if rate > 0 else 0
        qty = round(notional_usd / price, 4) if price > 0 else 0

        if qty <= 0:
            return

        # Broadcast Sure Call Signal if high confluence score
        if self.telegram and (abs(score) >= 30 or candidate.get("quant_score", 0) >= 30):
            asyncio.create_task(self.telegram.send_sure_call_signal(
                pair=pair,
                side="CALL" if direction == "LONG" else "PUT",
                current_price=price,
                rate=rate,
                win_probability=max(78.0, min(96.0, 50.0 + abs(score) * 0.45)),
                stop_loss=sl,
                take_profit_1=tp,
                take_profit_2=round(price * (1.035 if direction == "LONG" else 0.965), 4),
                take_profit_3=round(price * (1.055 if direction == "LONG" else 0.945), 4),
                confluence_reasons=[
                    f"Composite Quant Score: {score}/100",
                    f"Institutional Strategy: {strat_name}",
                    f"Risk-Managed {leverage}x Scalp Setup"
                ],
                leverage=leverage
            ))

        # 4. If Live mode active, dispatch order to CoinDCX with API confirmation
        if is_live:
            try:
                live_res = await self.client.create_futures_order_with_confirmation(
                    pair=pair,
                    side="buy" if direction == "LONG" else "sell",
                    order_type="market",
                    quantity=qty,
                    price=price,
                    leverage=leverage,
                    margin_currency="INR"
                )
                if live_res.get("success"):
                    self.log_action(
                        "LIVE_ENTRY",
                        f"{live_res.get('message')} [Strategy: {strat_name}, Lev: {leverage}x, Margin: ₹{margin_alloc_inr:,.0f}]",
                        {"pair": pair, "side": direction, "price": price, "qty": qty, "live": True, "res": live_res}
                    )
                    print(f"[AutoTrader] LIVE CoinDCX Order Confirmed: {pair} {direction} (ID: {live_res.get('order_id')})")
                    
                    # Broadcast Trade Executed alert to Telegram
                    if self.telegram:
                        asyncio.create_task(self.telegram.send_trade_opened(
                            pair=pair,
                            side="CALL" if direction == "LONG" else "PUT",
                            price=price,
                            quantity=qty,
                            leverage=leverage,
                            rate=rate,
                            margin_inr=margin_alloc_inr,
                            stop_loss=sl,
                            take_profit=tp,
                            trailing_sl_enabled=True,
                            trailing_offset_pct=trailing_offset,
                            strategy_name=strat_name,
                            is_live=True,
                            order_id=live_res.get("order_id")
                        ))
                    return
                else:
                    self.log_action(
                        "LIVE_ORDER_REJECTED",
                        f"{live_res.get('message')} | Guide: {live_res.get('guide')}",
                        {"pair": pair, "side": direction, "live": True, "res": live_res}
                    )
                    print(f"[AutoTrader] LIVE CoinDCX Order Rejected: {live_res.get('error')}")
                    return
            except Exception as e:
                self.log_action("ERROR", f"Live CoinDCX order execution exception: {e}", {"pair": pair})
                print(f"[AutoTrader] Live order error: {e}")
                return

        # 5. Track position in paper engine ONLY when in Paper Simulation mode
        res = self.paper.open_position(
            symbol=pair,
            side=direction,
            price=price,
            quantity=qty,
            leverage=leverage,
            stop_loss=sl,
            take_profit=tp,
            rate=rate,
            trailing_offset_pct=trailing_offset,
            strategy_name=strat_name,
            strategy_id=strat_id
        )

        if res.get("success"):
            self.log_action(
                "ENTRY",
                f"Opened {direction} on {pair} @ ${price:.4f} [Strategy: {strat_name}, Compounded Margin: ₹{margin_alloc_inr:,.0f}, Lev {leverage}x, Score {score}/100, SL: ${sl}, TP: ${tp}]",
                {"pair": pair, "side": direction, "price": price, "qty": qty, "margin_inr": margin_alloc_inr, "strategy": strat_name}
            )
            print(f"[AutoTrader] Entered position: {pair} {direction} @ ${price} [{strat_name}] (Margin: ₹{margin_alloc_inr:,.0f})")

        # Broadcast Paper Trade Executed alert to Telegram
        if self.telegram and res.get("success"):
            asyncio.create_task(self.telegram.send_trade_opened(
                pair=pair,
                side="CALL" if direction == "LONG" else "PUT",
                price=price,
                quantity=qty,
                leverage=leverage,
                rate=rate,
                margin_inr=margin_alloc_inr,
                stop_loss=sl,
                take_profit=tp,
                trailing_sl_enabled=True,
                trailing_offset_pct=trailing_offset,
                strategy_name=strat_name,
                is_live=False
            ))

    async def run_loop(self):
        """Continuous autonomous market evaluation loop."""
        print("[AutoTrader] Autonomous Agent Loop Started.")
        self.is_running = True
        
        while self.is_running and self.config.get("enabled", False):
            try:
                self.memory["last_scan_time"] = time.time()
                rate = await self.client.get_usdt_inr_rate()
                self.paper.set_usdt_inr_rate(rate)
                is_live = bool(self.config.get("live_trading_enabled", False) and self.client.api_key and self.client.secret_key)
                
                open_positions_count = 0
                if is_live:
                    # In LIVE mode, strictly check live positions from CoinDCX API
                    live_running = await self.client.get_futures_positions(margin_currency="INR", only_active=True)
                    open_positions_count = len(live_running)
                else:
                    # In PAPER mode, monitor paper simulation positions
                    acc = self.paper.get_summary()
                    positions = acc.get("positions", [])
                    open_positions_count = len(positions)
                    for pos in positions:
                        candles = await self.client.get_candles(pos["symbol"], interval="1m", limit=2)
                        if candles:
                            latest_price = float(candles[-1]["close"])
                            old_sl = pos.get("stop_loss")
                            exit_res = self.paper.update_mark_price(pos["symbol"], latest_price, rate=rate)
                            
                            # Log Trailing SL Ratchets
                            updated_pos = self.paper.state["positions"].get(pos["symbol"])
                            if updated_pos and updated_pos.get("stop_loss") != old_sl:
                                new_sl = updated_pos["stop_loss"]
                                pnl_inr = updated_pos.get("unrealized_pnl", 0.0)
                                pnl_pct = updated_pos.get("unrealized_pnl_pct", 0.0)
                                if updated_pos.get("trailing_sl_active"):
                                    print(f"[AutoTrader Trailing SL] {pos['symbol']} SL moved to ${new_sl} locking in ₹{pnl_inr:,.0f} (+{pnl_pct:.1f}%) profit!")
                                    self.log_action(
                                        "TRAILING_SL",
                                        f"Trailing SL adjusted to ${new_sl} on {pos['symbol']} (Securing ₹{pnl_inr:,.0f} / +{pnl_pct:.1f}% profit)",
                                        {"symbol": pos["symbol"], "sl": new_sl, "pnl_inr": pnl_inr}
                                    )

                            if exit_res and exit_res.get("closed_trade"):
                                closed = exit_res["closed_trade"]
                                await self.conduct_post_trade_autopsy(closed)

                                # Dispatch Target Hit or Stop Loss alert to Telegram
                                if self.telegram:
                                    reason = closed.get("reason", "")
                                    pnl_inr = closed.get("realized_pnl", 0.0)
                                    pnl_usdt = closed.get("pnl_usd", 0.0) or (pnl_inr / rate if rate > 0 else 0.0)
                                    roi = closed.get("roi_pct", 0.0) or closed.get("pnl_pct", 0.0)
                                    is_call = closed.get("side", "").upper() in ["BUY", "LONG"]
                                    
                                    if "TP" in reason.upper() or "TAKE_PROFIT" in reason.upper() or "QUICK_PROFIT" in reason.upper() or pnl_inr > 0:
                                        target_name = "Quick Profit Scalp Target" if "QUICK" in reason.upper() else "Take-Profit Target (TP1)"
                                        asyncio.create_task(self.telegram.send_target_hit(
                                            pair=closed.get("symbol", ""),
                                            side="CALL" if is_call else "PUT",
                                            entry_price=closed.get("entry_price", 0.0),
                                            exit_price=closed.get("exit_price", 0.0),
                                            quantity=closed.get("quantity", 0.0),
                                            realized_pnl_inr=pnl_inr,
                                            realized_pnl_usdt=pnl_usdt,
                                            roi_pct=roi,
                                            target_level=target_name,
                                            is_live=False
                                        ))
                                    else:
                                        asyncio.create_task(self.telegram.send_stoploss_hit(
                                            pair=closed.get("symbol", ""),
                                            side="CALL" if is_call else "PUT",
                                            entry_price=closed.get("entry_price", 0.0),
                                            exit_price=closed.get("exit_price", 0.0),
                                            realized_pnl_inr=pnl_inr,
                                            realized_pnl_usdt=pnl_usdt,
                                            roi_pct=roi,
                                            is_trailing=("TRAILING" in reason.upper()),
                                            is_live=False,
                                            learned_lesson=closed.get("learned_lesson")
                                        ))

                # If open position capacity available, scan high liquidity & momentum movers
                if open_positions_count < self.config["max_open_positions"]:
                    candidates = await self.scanner.get_high_liquidity_momentum_candidates(limit=25)
                    for item in candidates[:12]:
                        sym = item["symbol"]
                        analysis = await self.scanner.scan_single_pair(sym, interval="15m") # 15m tactical
                        if analysis and abs(analysis.get("score", 0)) >= self.config["min_score"]:
                            await self.execute_trade_decision(analysis)
                            await asyncio.sleep(1)

            except Exception as e:
                print(f"[AutoTrader] Loop error: {e}")

            # Sleep between scan cycles
            await asyncio.sleep(self.config.get("scan_interval_sec", 20))

        self.is_running = False
        print("[AutoTrader] Autonomous Agent Loop Stopped.")

    def start(self):
        """Start auto-trading task in background."""
        self.config["enabled"] = True
        self.save_memory()
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self.run_loop())
            self.log_action("SYSTEM", "Auto-Pilot Trading Enabled")

    def stop(self):
        """Stop auto-trading task."""
        self.config["enabled"] = False
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
        self.save_memory()
        self.log_action("SYSTEM", "Auto-Pilot Trading Paused")

    def reset_stats(self):
        """Reset all agent statistics, logs, and state to 0 for a fresh start."""
        self.memory["total_mistakes_avoided"] = 0
        self.memory["agent_activity_logs"] = []
        self.memory["last_scan_time"] = 0.0
        self.save_memory()
        self.learning_engine.state["total_mistakes_avoided"] = 0
        self.learning_engine.save()
        self.log_action("SYSTEM", "AutoTrader Stats and History Reset to 0")

    def get_status(self) -> Dict[str, Any]:
        """Return agent status, learned mistake rules, strategies, and logs."""
        return {
            "enabled": self.config.get("enabled", False),
            "is_running": self.is_running,
            "config": self.config,
            "mistakes_avoided": self.memory.get("total_mistakes_avoided", 0) + self.learning_engine.state.get("total_mistakes_avoided", 0),
            "learned_lessons_count": len(self.memory.get("learned_lessons", [])) + len(self.learning_engine.state.get("learned_mistake_rules", [])),
            "learned_lessons": self.memory.get("learned_lessons", [])[:10],
            "recent_logs": self.memory.get("agent_activity_logs", [])[:20],
            "last_scan_time": self.memory.get("last_scan_time", 0.0),
            "learning_summary": self.learning_engine.get_summary()
        }
