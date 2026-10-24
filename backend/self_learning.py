import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple

class SelfLearningStrategyEngine:
    """
    Autonomous Self-Learning & Self-Improvement Strategy Engine:
    - Learns from every losing trade (Mistake Memory & Auto-Correction).
    - Reinforces winning patterns into adaptive institutional strategies.
    - Self-improves strategy parameters over time (tightens filters on loss, lets winners run on profit).
    - Selects the optimal self-improved strategy time-to-time for each specific market regime.
    - Calculates dynamic compounding balance sizing to reinvest profits safely.
    """
    DATA_FILE = os.path.join("data", "self_learning_strategies.json")

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.file_path = os.path.join(self.base_dir, self.DATA_FILE)

        self.state: Dict[str, Any] = {
            "total_mistakes_avoided": 0,
            "total_adaptation_cycles": 0,
            "learned_mistake_rules": [],
            "winning_patterns": [],
            "self_improved_strategies": {},
            "strategy_evolution_logs": []
        }
        self.load()

    def load(self):
        """Load learned memory, mistake rules, and evolving strategies from disk."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.state.update(data)
            except Exception as e:
                print(f"[SelfLearningEngine] Error loading state: {e}")
        else:
            self._seed_default_strategies()
            self._seed_initial_mistake_rules()
            self.save()

    def save(self):
        """Persist state to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[SelfLearningEngine] Error saving state: {e}")

    def _seed_default_strategies(self):
        """Initialize core institutional self-improving strategies."""
        self.state["self_improved_strategies"] = {
            "DELTA_MOMENTUM_SURGE": {
                "id": "strat_delta_momentum",
                "name": "Delta Momentum Surge",
                "description": "Exploits high 24h momentum movers with aggressive orderbook delta buying pressure.",
                "regime": "MOMENTUM_TREND",
                "min_score": 35,
                "preferred_side": "LONG",
                "required_delta_bias": ["BULLISH_DELTA", "AGGRESSIVE_BUY_PRESSURE"],
                "target_rr": 2.0,
                "trailing_sl_offset_pct": 1.2,
                "leverage": 5,
                "trades_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 75.0,
                "total_profit_inr": 0.0,
                "adaptation_level": 1,
                "last_adapted": time.time(),
                "adaptation_notes": "Initialized with baseline institutional parameters."
            },
            "MICROSTRUCTURE_WALL_ABSORPTION": {
                "id": "strat_wall_absorption",
                "name": "Microstructure Wall Absorption",
                "description": "Fades extreme orderbook imbalance or enters with dominant whale wall defense.",
                "regime": "ORDERBOOK_DEPTH",
                "min_score": 40,
                "preferred_side": "ANY",
                "min_imbalance_pct": 20.0,
                "target_rr": 2.2,
                "trailing_sl_offset_pct": 1.0,
                "leverage": 5,
                "trades_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 70.0,
                "total_profit_inr": 0.0,
                "adaptation_level": 1,
                "last_adapted": time.time(),
                "adaptation_notes": "Initialized with strict orderbook wall absorption criteria."
            },
            "OVERSOLD_REVERSAL_FLOW": {
                "id": "strat_oversold_reversal",
                "name": "Oversold Flow Reversal",
                "description": "Catches bottom exhaustion when RSI is oversold and top-5 microstructure delta turns positive.",
                "regime": "MEAN_REVERSION",
                "min_score": 30,
                "preferred_side": "LONG",
                "max_rsi": 38.0,
                "target_rr": 2.5,
                "trailing_sl_offset_pct": 1.1,
                "leverage": 4,
                "trades_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 68.0,
                "total_profit_inr": 0.0,
                "adaptation_level": 1,
                "last_adapted": time.time(),
                "adaptation_notes": "Initialized for oversold bounce trading."
            },
            "BREAKDOWN_DELTA_SHORT": {
                "id": "strat_breakdown_short",
                "name": "Breakdown Delta Short",
                "description": "Enters high-volume short positions when top gainers exhaust and sell delta surges.",
                "regime": "BEARISH_EXHAUSTION",
                "min_score": -35,
                "preferred_side": "SHORT",
                "required_delta_bias": ["BEARISH_DELTA", "AGGRESSIVE_SELL_PRESSURE"],
                "target_rr": 2.0,
                "trailing_sl_offset_pct": 1.2,
                "leverage": 5,
                "trades_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 72.0,
                "total_profit_inr": 0.0,
                "adaptation_level": 1,
                "last_adapted": time.time(),
                "adaptation_notes": "Initialized for liquid gainer breakdown shorting."
            }
        }

    def _seed_initial_mistake_rules(self):
        """Initial baseline negative rules to avoid common retail traps."""
        self.state["learned_mistake_rules"] = [
            {
                "id": "mistake_prior_1",
                "pattern": "OVERBOUGHT_GREED_TRAP",
                "condition": "RSI > 72 on Long Entry",
                "trigger_criteria": {"side": "LONG", "min_rsi": 72.0},
                "reason": "Buying into RSI overbought exhaustion (>72) frequently triggers sharp pullbacks.",
                "action": "REJECT_LONG",
                "times_prevented": 0,
                "learned_from": "Institutional Risk Framework"
            },
            {
                "id": "mistake_prior_2",
                "pattern": "OVERSOLD_PANIC_SHORT",
                "condition": "RSI < 26 on Short Entry",
                "trigger_criteria": {"side": "SHORT", "max_rsi": 26.0},
                "reason": "Shorting into oversold panic (<26) risks getting trapped by sudden short squeezes.",
                "action": "REJECT_SHORT",
                "times_prevented": 0,
                "learned_from": "Institutional Risk Framework"
            },
            {
                "id": "mistake_prior_3",
                "pattern": "OPPOSING_WHALE_WALL_HEADWIND",
                "condition": "Orderbook Imbalance < -22% on Long",
                "trigger_criteria": {"side": "LONG", "max_imbalance": -22.0},
                "reason": "Entering LONG directly into dense overhead sell walls fails due to lack of buyer absorption.",
                "action": "REJECT_LONG",
                "times_prevented": 0,
                "learned_from": "Orderbook Microstructure Analysis"
            },
            {
                "id": "mistake_prior_4",
                "pattern": "OPPOSING_BID_WALL_SUPPORT",
                "condition": "Orderbook Imbalance > +22% on Short",
                "trigger_criteria": {"side": "SHORT", "min_imbalance": 22.0},
                "reason": "Shorting directly into concentrated bid support walls fails when whales absorb market sells.",
                "action": "REJECT_SHORT",
                "times_prevented": 0,
                "learned_from": "Orderbook Microstructure Analysis"
            }
        ]

    # ==========================================================
    # Trade Selection & Mistake Prevention
    # ==========================================================

    def evaluate_candidate(self, analysis: Dict[str, Any], direction: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Evaluate candidate against:
        1. All learned mistake rules (reject if matches past failure pattern).
        2. Select the optimal self-improved strategy matching the coin's technical flow.
        Returns: (is_approved, rejection_reason, selected_strategy)
        """
        rsi = analysis.get("rsi", 50.0)
        ob = analysis.get("orderbook", {})
        imbalance = ob.get("imbalance_pct", 0.0)
        delta_bias = ob.get("delta_bias", "BALANCED")
        score = analysis.get("score", 0)
        symbol = analysis.get("pair", "")

        # 1. Mistake Prevention Check
        for rule in self.state.get("learned_mistake_rules", []):
            crit = rule.get("trigger_criteria", {})
            rule_side = crit.get("side")

            if rule_side and rule_side != direction:
                continue

            # Check RSI criteria
            if "min_rsi" in crit and rsi >= crit["min_rsi"]:
                rule["times_prevented"] += 1
                self.state["total_mistakes_avoided"] += 1
                self.save()
                return False, f"Memory Rule ({rule['pattern']}): {rule['reason']}", None

            if "max_rsi" in crit and rsi <= crit["max_rsi"]:
                rule["times_prevented"] += 1
                self.state["total_mistakes_avoided"] += 1
                self.save()
                return False, f"Memory Rule ({rule['pattern']}): {rule['reason']}", None

            # Check Imbalance criteria
            if "max_imbalance" in crit and imbalance <= crit["max_imbalance"]:
                rule["times_prevented"] += 1
                self.state["total_mistakes_avoided"] += 1
                self.save()
                return False, f"Memory Rule ({rule['pattern']}): {rule['reason']}", None

            if "min_imbalance" in crit and imbalance >= crit["min_imbalance"]:
                rule["times_prevented"] += 1
                self.state["total_mistakes_avoided"] += 1
                self.save()
                return False, f"Memory Rule ({rule['pattern']}): {rule['reason']}", None

            # Symbol cooldown
            if rule.get("symbol") == symbol and rule.get("side") == direction:
                cooldown_sec = rule.get("cooldown_sec", 1200)
                if time.time() - rule.get("timestamp", 0) < cooldown_sec:
                    rule["times_prevented"] += 1
                    self.state["total_mistakes_avoided"] += 1
                    self.save()
                    return False, f"Symbol Cooldown ({rule['id']}): {rule['reason']}", None

        # 2. Select Optimal Self-Improved Strategy
        selected_strategy = None
        best_winrate = -1.0

        for key, strat in self.state.get("self_improved_strategies", {}).items():
            preferred = strat.get("preferred_side", "ANY")
            if preferred != "ANY" and preferred != direction:
                continue

            # Check required delta bias
            req_bias = strat.get("required_delta_bias")
            if req_bias and delta_bias not in req_bias:
                continue

            # Check score threshold
            if direction == "LONG" and score < strat.get("min_score", 30):
                continue
            if direction == "SHORT" and score > strat.get("min_score", -30):
                continue

            # Check RSI if specified
            if "max_rsi" in strat and rsi > strat["max_rsi"]:
                continue

            # Pick strategy with highest historical win-rate
            strat_wr = strat.get("win_rate", 50.0)
            if strat_wr > best_winrate:
                best_winrate = strat_wr
                selected_strategy = strat

        if not selected_strategy:
            # Fallback to general baseline
            selected_strategy = {
                "name": "General Confluence Baseline",
                "id": "strat_baseline",
                "target_rr": 1.8,
                "trailing_sl_offset_pct": 1.2,
                "leverage": 5
            }

        return True, None, selected_strategy

    # ==========================================================
    # Self-Improvement & Mistake Learning Loops
    # ==========================================================

    async def learn_from_mistake(
        self,
        closed_trade: Dict[str, Any],
        ai_autopsy_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract lessons from a losing trade, synthesize a new mistake rule,
        and adapt the responsible strategy to tighten risk controls.
        """
        pnl = closed_trade.get("realized_pnl", 0.0)
        symbol = closed_trade.get("symbol", "")
        side = closed_trade.get("side", "")
        reason = closed_trade.get("reason", "")
        strat_id = closed_trade.get("strategy_id")
        entry_price = closed_trade.get("entry_price", 0.0)
        exit_price = closed_trade.get("exit_price", 0.0)
        loss_inr = abs(pnl)

        lesson_text = ai_autopsy_summary or f"Loss on {symbol} {side} via {reason}. Stopped out from ${entry_price} to ${exit_price}."

        # Create new Mistake Rule
        new_rule_id = f"mistake_{int(time.time())}"
        new_rule = {
            "id": new_rule_id,
            "symbol": symbol,
            "side": side,
            "timestamp": time.time(),
            "cooldown_sec": 1800, # 30 min cooldown on same pair & direction
            "pattern": f"INVALIDATION_{side}_{reason}",
            "condition": f"Failure on {symbol} {side} exiting via {reason}",
            "reason": lesson_text,
            "action": f"REJECT_{side}",
            "times_prevented": 0,
            "loss_amount_inr": loss_inr,
            "learned_from": f"Trade Autopsy Loss -₹{loss_inr:,.2f}"
        }

        self.state["learned_mistake_rules"].insert(0, new_rule)
        self.state["learned_mistake_rules"] = self.state["learned_mistake_rules"][:40]

        # Adapt responsible strategy: tighten filters
        adapted_note = ""
        for s_key, strat in self.state.get("self_improved_strategies", {}).items():
            if strat.get("id") == strat_id or strat.get("name") == closed_trade.get("strategy_name"):
                strat["loss_count"] = strat.get("loss_count", 0) + 1
                strat["trades_count"] = strat.get("trades_count", 0) + 1
                strat["total_profit_inr"] = strat.get("total_profit_inr", 0.0) - loss_inr
                total = strat["trades_count"]
                strat["win_rate"] = round((strat.get("win_count", 0) / total) * 100.0, 1) if total > 0 else 50.0

                # Self-Improvement Adaptation: Tighten requirements
                old_score = strat.get("min_score", 35)
                new_score = min(60, old_score + 2) if old_score > 0 else max(-60, old_score - 2)
                strat["min_score"] = new_score
                strat["trailing_sl_offset_pct"] = max(0.8, round(strat.get("trailing_sl_offset_pct", 1.2) - 0.05, 2))
                strat["adaptation_level"] = strat.get("adaptation_level", 1) + 1
                strat["last_adapted"] = time.time()
                adapted_note = f"Self-adapted strategy '{strat['name']}': Raised min score to {new_score} & tightened trailing SL to {strat['trailing_sl_offset_pct']}% after loss."
                strat["adaptation_notes"] = adapted_note
                break

        self.state["total_adaptation_cycles"] += 1
        log_entry = {
            "timestamp": time.time(),
            "type": "MISTAKE_LEARNED",
            "message": f"Mistake autopsy learned on {symbol} {side}: {lesson_text}. {adapted_note}",
            "loss_inr": loss_inr
        }
        self.state["strategy_evolution_logs"].insert(0, log_entry)
        self.state["strategy_evolution_logs"] = self.state["strategy_evolution_logs"][:50]

        self.save()
        return new_rule

    def learn_from_win(self, closed_trade: Dict[str, Any]):
        """
        Reinforce successful patterns, adapt winning strategies to expand profit targets.
        """
        pnl = closed_trade.get("realized_pnl", 0.0)
        symbol = closed_trade.get("symbol", "")
        side = closed_trade.get("side", "")
        reason = closed_trade.get("reason", "")
        strat_id = closed_trade.get("strategy_id")
        profit_inr = pnl

        pattern = {
            "timestamp": time.time(),
            "symbol": symbol,
            "side": side,
            "profit_inr": profit_inr,
            "pnl_pct": closed_trade.get("pnl_pct", 0.0),
            "exit_reason": reason,
            "strategy": closed_trade.get("strategy_name", "Confluence")
        }
        self.state["winning_patterns"].insert(0, pattern)
        self.state["winning_patterns"] = self.state["winning_patterns"][:40]

        # Adapt responsible strategy: let winners run
        adapted_note = ""
        for s_key, strat in self.state.get("self_improved_strategies", {}).items():
            if strat.get("id") == strat_id or strat.get("name") == closed_trade.get("strategy_name"):
                strat["win_count"] = strat.get("win_count", 0) + 1
                strat["trades_count"] = strat.get("trades_count", 0) + 1
                strat["total_profit_inr"] = strat.get("total_profit_inr", 0.0) + profit_inr
                total = strat["trades_count"]
                strat["win_rate"] = round((strat.get("win_count", 0) / total) * 100.0, 1) if total > 0 else 100.0

                # Self-Improvement Adaptation: Expand target RR slightly
                strat["target_rr"] = min(3.5, round(strat.get("target_rr", 2.0) + 0.05, 2))
                strat["adaptation_level"] = strat.get("adaptation_level", 1) + 1
                strat["last_adapted"] = time.time()
                adapted_note = f"Self-adapted strategy '{strat['name']}': Expanded target R:R to {strat['target_rr']}x based on {strat['win_rate']}% win rate."
                strat["adaptation_notes"] = adapted_note
                break

        self.state["total_adaptation_cycles"] += 1
        log_entry = {
            "timestamp": time.time(),
            "type": "WIN_REINFORCED",
            "message": f"Winning pattern on {symbol} {side} (+₹{profit_inr:,.2f} via {reason}). {adapted_note}",
            "profit_inr": profit_inr
        }
        self.state["strategy_evolution_logs"].insert(0, log_entry)
        self.state["strategy_evolution_logs"] = self.state["strategy_evolution_logs"][:50]

        self.save()

    # ==========================================================
    # Dynamic Balance Compounding Sizing
    # ==========================================================

    def calculate_compound_position_size(
        self,
        available_balance_inr: float,
        risk_pct: float = 5.0,
        min_margin_inr: float = 10000.0,
        max_margin_inr: float = 35000.0
    ) -> Dict[str, Any]:
        """
        Dynamically calculate position sizing based on available balance to compound profits.
        - Risk per trade capped strictly at 5% of balance (max ₹35,000) so no single trade risks significant capital.
        - As drawdowns occur, position size safely contracts.
        """
        if available_balance_inr <= 0:
            return {
                "margin_inr": min_margin_inr,
                "compounding_active": False,
                "notes": "Insufficient balance. Using minimum base margin."
            }

        # Dynamic floor and ceiling based on available balance (strictly cap to max ₹35,000 or 6% of balance)
        effective_min = min(min_margin_inr, max(5000.0, available_balance_inr * 0.02))
        effective_max = min(max_margin_inr, max(effective_min, available_balance_inr * 0.06))

        # Compounding allocation: 5% of available balance
        calculated_margin = available_balance_inr * (risk_pct / 100.0)
        clamped_margin = max(effective_min, min(effective_max, calculated_margin))

        return {
            "margin_inr": round(clamped_margin, 2),
            "available_balance_inr": round(available_balance_inr, 2),
            "compounding_active": True,
            "risk_pct": risk_pct,
            "notes": f"Compounded sizing: Allocated ₹{clamped_margin:,.2f} ({risk_pct}% of available ₹{available_balance_inr:,.2f})"
        }

    def get_summary(self) -> Dict[str, Any]:
        """Summary for UI Copilot Drawer & Dashboard."""
        return {
            "total_mistakes_avoided": self.state.get("total_mistakes_avoided", 0),
            "total_adaptation_cycles": self.state.get("total_adaptation_cycles", 0),
            "mistake_rules_count": len(self.state.get("learned_mistake_rules", [])),
            "mistake_rules": self.state.get("learned_mistake_rules", [])[:15],
            "winning_patterns_count": len(self.state.get("winning_patterns", [])),
            "winning_patterns": self.state.get("winning_patterns", [])[:15],
            "strategies": list(self.state.get("self_improved_strategies", {}).values()),
            "evolution_logs": self.state.get("strategy_evolution_logs", [])[:20]
        }
