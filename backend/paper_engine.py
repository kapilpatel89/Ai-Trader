import os
import json
import time
from typing import Dict, Any, List, Optional

class PaperTradingEngine:
    """
    CoinDCX INR Futures Trading Simulator.
    Denominates balance, margin, and PnL directly in Indian Rupees (₹ INR),
    settling crypto contracts using live USDT/INR market rate.
    """
    DATA_FILE = os.path.join("data", "paper_account.json")

    def __init__(self, initial_balance_inr: float = 1000000.0, usdt_inr_rate: float = 100.74):
        self.initial_balance = initial_balance_inr
        self.usdt_inr_rate = usdt_inr_rate
        self.currency = "INR"
        self.currency_symbol = "₹"
        self.state: Dict[str, Any] = {
            "currency": "INR",
            "currency_symbol": "₹",
            "balance": initial_balance_inr,
            "starting_balance": initial_balance_inr,
            "realized_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "positions": {},       # symbol -> position dict
            "trade_history": []    # closed trades
        }
        self.load()

    def set_usdt_inr_rate(self, rate: float):
        if rate and rate > 0:
            self.usdt_inr_rate = rate

    def load(self):
        """Load state from data/paper_account.json if exists."""
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # If legacy USD balance (< 50,000), upgrade to INR
                    if data.get("balance", 0) < 50000:
                        data["balance"] = round(data.get("balance", 10000) * 100.0, 2)
                        data["starting_balance"] = round(data.get("starting_balance", 10000) * 100.0, 2)
                        data["realized_pnl"] = round(data.get("realized_pnl", 0) * 100.0, 2)
                    data["currency"] = "INR"
                    data["currency_symbol"] = "₹"
                    self.state.update(data)
            except Exception as e:
                print(f"[PaperEngine] Error loading state: {e}")

    def save(self):
        """Save current state to disk."""
        os.makedirs(os.path.dirname(self.DATA_FILE), exist_ok=True)
        try:
            with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[PaperEngine] Error saving state: {e}")

    def reset(self, new_balance_inr: float = 1000000.0):
        """Reset virtual INR paper trading portfolio."""
        self.state = {
            "currency": "INR",
            "currency_symbol": "₹",
            "balance": new_balance_inr,
            "starting_balance": new_balance_inr,
            "realized_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "positions": {},
            "trade_history": []
        }
        self.save()
        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        """Calculate total account equity in INR including unrealized PnL."""
        unrealized_total_inr = 0.0
        used_margin_inr = 0.0
        
        positions_list = []
        for sym, pos in self.state["positions"].items():
            unrealized_total_inr += pos.get("unrealized_pnl", 0.0)
            used_margin_inr += pos.get("margin", 0.0)
            positions_list.append(pos)

        equity_inr = self.state["balance"] + used_margin_inr + unrealized_total_inr
        total_pnl_inr = equity_inr - self.state["starting_balance"]
        total_pnl_pct = (total_pnl_inr / (self.state["starting_balance"] + 1e-9)) * 100.0

        total_trades = self.state["total_trades"]
        win_rate = (self.state["winning_trades"] / total_trades * 100.0) if total_trades > 0 else 0.0

        return {
            "currency": "INR",
            "currency_symbol": "₹",
            "usdt_inr_rate": self.usdt_inr_rate,
            "balance": round(self.state["balance"], 2),
            "equity": round(equity_inr, 2),
            "used_margin": round(used_margin_inr, 2),
            "free_margin": round(self.state["balance"], 2),
            "unrealized_pnl": round(unrealized_total_inr, 2),
            "realized_pnl": round(self.state["realized_pnl"], 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "active_positions_count": len(positions_list),
            "positions": positions_list,
            "trade_history": list(reversed(self.state.get("trade_history", [])))[:100] # Up to 100 recent trades (newest first)
        }

    def open_position(
        self,
        symbol: str,
        side: str,  # 'LONG' or 'SHORT'
        price: float,
        quantity: float,
        leverage: int = 5,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        rate: Optional[float] = None,
        trailing_offset_pct: Optional[float] = None,
        trailing_sl_enabled: bool = True,
        margin_currency: str = "INR",
        strategy_name: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Open a new CoinDCX futures position with isolated margin (INR or USDT)."""
        side = side.upper()
        if side not in ["LONG", "SHORT"]:
            return {"error": "Invalid side. Must be LONG or SHORT."}
        
        if price <= 0 or quantity <= 0:
            return {"error": "Price and quantity must be positive."}

        conversion_rate = rate or self.usdt_inr_rate
        notional_value_usdt = price * quantity
        notional_value_inr = notional_value_usdt * conversion_rate
        margin_required_inr = notional_value_inr / leverage

        if self.state["balance"] < margin_required_inr:
            return {
                "error": f"Insufficient margin. Required: ₹{margin_required_inr:,.2f}, Available: ₹{self.state['balance']:,.2f}"
            }

        # Deduct margin from free balance
        self.state["balance"] -= margin_required_inr

        # Estimated liquidation price
        if side == "LONG":
            liq_price = price * (1.0 - (0.9 / leverage))
        else:
            liq_price = price * (1.0 + (0.9 / leverage))

        effective_trailing_offset = trailing_offset_pct or (1.0 if leverage <= 5 else 0.8)

        position_data = {
            "id": f"pos_{int(time.time() * 1000)}",
            "symbol": symbol,
            "side": side,
            "entry_price": round(price, 4),
            "entry_price_inr": round(price * conversion_rate, 2),
            "mark_price": round(price, 4),
            "mark_price_inr": round(price * conversion_rate, 2),
            "quantity": round(quantity, 4),
            "leverage": leverage,
            "margin_currency": margin_currency.upper(),
            "notional_usdt": round(notional_value_usdt, 2),
            "notional": round(notional_value_inr, 2),
            "margin": round(margin_required_inr, 2),
            "liquidation_price": round(liq_price, 4),
            "stop_loss": round(stop_loss, 4) if stop_loss else None,
            "initial_stop_loss": round(stop_loss, 4) if stop_loss else None,
            "take_profit": round(take_profit, 4) if take_profit else None,
            "highest_price": round(price, 4),
            "lowest_price": round(price, 4),
            "highest_pnl_pct": 0.0,
            "trailing_sl_enabled": bool(trailing_sl_enabled),
            "trailing_sl_active": False,
            "trailing_offset_pct": round(effective_trailing_offset, 2),
            "breakeven_activated": False,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "usdt_inr_rate": conversion_rate,
            "strategy_name": strategy_name or "Confluence",
            "strategy_id": strategy_id or "strat_default",
            "open_time": time.time()
        }

        self.state["positions"][symbol] = position_data
        self.save()
        return {"success": True, "position": position_data, "account": self.get_summary()}

    def update_mark_price(self, symbol: str, current_price: float, rate: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Update open position mark price, compute INR PnL, manage dynamic
        trailing stop-loss in profit, check SL/TP and liquidations.
        """
        if symbol not in self.state["positions"] or current_price <= 0:
            return None

        pos = self.state["positions"][symbol]
        conversion_rate = rate or pos.get("usdt_inr_rate") or self.usdt_inr_rate
        pos["mark_price"] = current_price
        pos["mark_price_inr"] = round(current_price * conversion_rate, 2)
        entry = pos["entry_price"]
        qty = pos["quantity"]
        side = pos["side"]

        if side == "LONG":
            pnl_usdt = (current_price - entry) * qty
        else:
            pnl_usdt = (entry - current_price) * qty

        pnl_inr = pnl_usdt * conversion_rate
        pos["unrealized_pnl"] = round(pnl_inr, 2)
        pos["unrealized_pnl_pct"] = round((pnl_inr / (pos["margin"] + 1e-9)) * 100.0, 2)

        pnl_pct = pos["unrealized_pnl_pct"]
        trail_offset_pct = pos.get("trailing_offset_pct", 1.2)
        trade_duration_sec = time.time() - pos.get("open_time", time.time())

        # ==========================================================
        # 1. STRICT LOSS CONTROL: HARD RISK & DRAWDOWN CAP (-2.0% or ₹2,500 MAX)
        # ==========================================================
        # No single trade is ever permitted to exceed -2.0% margin loss (or max ₹2,500 drawdown).
        # This completely prevents disastrous -6% to -13% losses seen in earlier history!
        if pnl_pct <= -2.0 or pnl_inr <= -2500.0:
            return self.close_position(
                symbol,
                exit_price=current_price,
                reason="MAX_LOSS_CAP_PROTECTION",
                rate=conversion_rate
            )

        # ==========================================================
        # 2. STAGNATION CUT (TIME-BASED INVALIDATION)
        # ==========================================================
        # If a scalp trade hovers in negative PnL for > 45 minutes without making progress,
        # cut the loss immediately to avoid prolonged bleeding.
        if trade_duration_sec > 2700 and pnl_pct <= -0.8:
            return self.close_position(
                symbol,
                exit_price=current_price,
                reason="STAGNATION_TIME_CUT",
                rate=conversion_rate
            )

        # ==========================================================
        # 3. DYNAMIC TRAILING PROFIT LOCK & FAST BREAKEVEN
        # ==========================================================
        if side == "LONG":
            if current_price > pos.get("highest_price", entry):
                pos["highest_price"] = current_price
            if pnl_pct > pos.get("highest_pnl_pct", 0.0):
                pos["highest_pnl_pct"] = pnl_pct

            # Tier 1: Fast Breakeven Lock (Trigger at >= +0.45% profit to lock in zero risk)
            if pnl_pct >= 0.45 and not pos.get("breakeven_activated", False):
                be_sl = round(entry * 1.0012, 4)  # Entry + 0.12% fee buffer
                if pos.get("stop_loss") is None or be_sl > pos["stop_loss"]:
                    pos["stop_loss"] = be_sl
                    pos["breakeven_activated"] = True
                    pos["trailing_sl_active"] = True

            # Tier 2: Profit Preservation Trailing Stop (Trigger at >= +1.2% profit)
            if pnl_pct >= 1.2:
                pos["trailing_sl_active"] = True
                # Lock percentage of peak gain directly in price
                lock_ratio = 0.80 if pnl_pct >= 3.5 else 0.70 if pnl_pct >= 2.0 else 0.50
                locked_gain_price = entry + ((pos["highest_price"] - entry) * lock_ratio)
                trail_sl = round(locked_gain_price, 4)
                if pos.get("stop_loss") is None or trail_sl > pos["stop_loss"]:
                    pos["stop_loss"] = trail_sl

            # Tier 3: Quick Profit Protection (Avoid giving back >= 40% of peak gains once >= +1.5%)
            if pos.get("highest_pnl_pct", 0.0) >= 1.5 and pnl_pct <= pos["highest_pnl_pct"] * 0.60:
                return self.close_position(symbol, exit_price=current_price, reason="QUICK_PROFIT_PROTECTION", rate=conversion_rate)

        elif side == "SHORT":
            if current_price < pos.get("lowest_price", entry):
                pos["lowest_price"] = current_price
            if pnl_pct > pos.get("highest_pnl_pct", 0.0):
                pos["highest_pnl_pct"] = pnl_pct

            # Tier 1: Fast Breakeven Lock (Trigger at >= +0.45% profit)
            if pnl_pct >= 0.45 and not pos.get("breakeven_activated", False):
                be_sl = round(entry * 0.9988, 4)  # Entry - 0.12% fee buffer
                if pos.get("stop_loss") is None or be_sl < pos["stop_loss"]:
                    pos["stop_loss"] = be_sl
                    pos["breakeven_activated"] = True
                    pos["trailing_sl_active"] = True

            # Tier 2: Profit Preservation Trailing Stop (Trigger at >= +1.2% profit)
            if pnl_pct >= 1.2:
                pos["trailing_sl_active"] = True
                lock_ratio = 0.80 if pnl_pct >= 3.5 else 0.70 if pnl_pct >= 2.0 else 0.50
                locked_gain_price = entry - ((entry - pos["lowest_price"]) * lock_ratio)
                trail_sl = round(locked_gain_price, 4)
                if pos.get("stop_loss") is None or trail_sl < pos["stop_loss"]:
                    pos["stop_loss"] = trail_sl

            # Tier 3: Quick Profit Protection
            if pos.get("highest_pnl_pct", 0.0) >= 1.5 and pnl_pct <= pos["highest_pnl_pct"] * 0.60:
                return self.close_position(symbol, exit_price=current_price, reason="QUICK_PROFIT_PROTECTION", rate=conversion_rate)

        # Check Stop-Loss / Trailing Stop Trigger
        sl = pos.get("stop_loss")
        if sl:
            if (side == "LONG" and current_price <= sl) or (side == "SHORT" and current_price >= sl):
                reason = "TRAILING_STOP_PROFIT_TRIGGERED" if (pos.get("trailing_sl_active") and pnl_inr > 0) else "STOP_LOSS_TRIGGERED"
                return self.close_position(symbol, exit_price=sl, reason=reason, rate=conversion_rate)

        # Check Take-Profit Trigger
        tp = pos.get("take_profit")
        if tp:
            if (side == "LONG" and current_price >= tp) or (side == "SHORT" and current_price <= tp):
                return self.close_position(symbol, exit_price=tp, reason="TAKE_PROFIT_TRIGGERED", rate=conversion_rate)

        # Check Liquidation
        liq = pos.get("liquidation_price")
        if liq:
            if (side == "LONG" and current_price <= liq) or (side == "SHORT" and current_price >= liq):
                return self.close_position(symbol, exit_price=liq, reason="LIQUIDATED", rate=conversion_rate)

        return None

    def close_position(
        self,
        symbol: str,
        exit_price: Optional[float] = None,
        reason: str = "MANUAL_CLOSE",
        rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """Close active position, realize PnL in INR, return margin to balance."""
        if symbol not in self.state["positions"]:
            return {"error": f"No active position for {symbol}"}

        pos = self.state["positions"].pop(symbol)
        conversion_rate = rate or pos.get("usdt_inr_rate") or self.usdt_inr_rate
        price = exit_price or pos.get("mark_price", pos["entry_price"])
        side = pos["side"]
        qty = pos["quantity"]
        entry = pos["entry_price"]

        if side == "LONG":
            pnl_usdt = (price - entry) * qty
        else:
            pnl_usdt = (entry - price) * qty

        pnl_inr = round(pnl_usdt * conversion_rate, 2)
        returned_cash_inr = max(0.0, pos["margin"] + pnl_inr)
        
        self.state["balance"] += returned_cash_inr
        self.state["realized_pnl"] += pnl_inr
        self.state["total_trades"] += 1
        
        if pnl_inr > 0:
            self.state["winning_trades"] += 1
        else:
            self.state["losing_trades"] += 1

        closed_record = {
            "id": pos.get("id"),
            "symbol": symbol,
            "side": side,
            "entry_price": entry,
            "entry_price_inr": round(entry * conversion_rate, 2),
            "exit_price": round(price, 4),
            "exit_price_inr": round(price * conversion_rate, 2),
            "quantity": qty,
            "leverage": pos["leverage"],
            "margin": pos["margin"],
            "margin_currency": "INR",
            "realized_pnl": pnl_inr,
            "pnl": pnl_inr,
            "pnl_inr": pnl_inr,
            "pnl_pct": round((pnl_inr / (pos["margin"] + 1e-9)) * 100.0, 2),
            "reason": reason,
            "strategy_name": pos.get("strategy_name", "Confluence"),
            "strategy_id": pos.get("strategy_id", "strat_default"),
            "close_time": time.time(),
            "duration_sec": int(time.time() - pos.get("open_time", time.time()))
        }

        self.state["trade_history"].append(closed_record)
        self.save()

        return {
            "success": True,
            "closed_trade": closed_record,
            "account": self.get_summary()
        }
