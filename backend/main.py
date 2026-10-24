import os
import sys
import json
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Body, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .coindcx_client import CoinDCXClient
from .technical_analysis import TechnicalAnalysis
from .scanner import MarketScanner
from .llm_engine import LLMEngine
from .paper_engine import PaperTradingEngine
from .auto_trader import AutoTradingAgent
from .telegram_notifier import TelegramNotifier

# App Directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Persistent Settings
def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "coindcx_key": "",
        "coindcx_secret": "",
        "live_trading_enabled": False,
        "default_leverage": 5,
        "selected_model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "telegram_enabled": False,
        "telegram_signals_enabled": False,
        "telegram_trades_enabled": False
    }

def save_config(cfg: Dict[str, Any]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# Initialize core services
coindcx = CoinDCXClient(
    api_key=config.get("coindcx_key", ""),
    secret_key=config.get("coindcx_secret", "")
)
scanner = MarketScanner(coindcx)
llm = LLMEngine(base_dir=BASE_DIR)
paper = PaperTradingEngine()
telegram = TelegramNotifier(
    bot_token=config.get("telegram_bot_token", ""),
    chat_id=config.get("telegram_chat_id", ""),
    enabled=config.get("telegram_enabled", True),
    signals_enabled=config.get("telegram_signals_enabled", True),
    trades_enabled=config.get("telegram_trades_enabled", True)
)
auto_trader = AutoTradingAgent(coindcx, scanner, llm, paper, telegram=telegram)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure local LLM is active in background with GPU priority
    print("[System] Initializing CoinDCX AI Trading Terminal...")
    asyncio.create_task(llm.start_server(config.get("selected_model")))
    # Initial quick scan in background (15m tactical + 1h macro trend)
    asyncio.create_task(scanner.run_full_scan(top_n=25, interval="15m"))
    if auto_trader.config.get("enabled", False):
        auto_trader.start()
    yield
    # Shutdown: Keep local LLM alive in GPU memory for instant restart
    print("[System] Preserving local LLM in GPU memory...")
    auto_trader.stop()
    await coindcx.close()
    await telegram.close()

app = FastAPI(title="CoinDCX AI Institutional Futures Terminal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(
                content=f.read(),
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    return HTMLResponse("<h1>CoinDCX AI Terminal Loading...</h1>")

# ==========================================================
# REST API: System Status & Configuration
# ==========================================================

@app.get("/api/status")
async def get_system_status():
    models = llm.find_models()
    llm_health = await llm.check_health()
    return {
        "status": "online",
        "llm": {
            "ready": llm_health,
            "port": llm.port,
            "active_model": llm.active_model_name or (models[0] if models else "None"),
            "available_models": models,
            "gpu_first": True
        },
        "coindcx": {
            "has_keys": bool(coindcx.api_key and coindcx.secret_key),
            "live_mode": config.get("live_trading_enabled", False)
        },
        "telegram": {
            "configured": bool(telegram.bot_token and telegram.chat_id),
            "enabled": telegram.enabled,
            "signals_enabled": telegram.signals_enabled,
            "trades_enabled": telegram.trades_enabled,
            "chat_id": telegram.chat_id
        },
        "scanner": scanner.scan_progress
    }

class ConfigUpdate(BaseModel):
    coindcx_key: Optional[str] = None
    coindcx_secret: Optional[str] = None
    live_trading_enabled: Optional[bool] = None
    default_leverage: Optional[int] = None
    selected_model: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    telegram_signals_enabled: Optional[bool] = None
    telegram_trades_enabled: Optional[bool] = None

@app.post("/api/settings")
async def update_settings(data: ConfigUpdate):
    global config
    if data.coindcx_key is not None:
        config["coindcx_key"] = data.coindcx_key
        coindcx.api_key = data.coindcx_key
    if data.coindcx_secret is not None:
        config["coindcx_secret"] = data.coindcx_secret
        coindcx.secret_key = data.coindcx_secret
    if data.live_trading_enabled is not None:
        config["live_trading_enabled"] = data.live_trading_enabled
        auto_trader.config["live_trading_enabled"] = data.live_trading_enabled
    if data.default_leverage is not None:
        config["default_leverage"] = data.default_leverage
    if data.selected_model is not None and data.selected_model != llm.active_model_name:
        config["selected_model"] = data.selected_model
        llm.stop_server()
        asyncio.create_task(llm.start_server(data.selected_model))
    if data.telegram_bot_token is not None:
        config["telegram_bot_token"] = data.telegram_bot_token.strip()
    if data.telegram_chat_id is not None:
        config["telegram_chat_id"] = str(data.telegram_chat_id).strip()
    if data.telegram_enabled is not None:
        config["telegram_enabled"] = data.telegram_enabled
    if data.telegram_signals_enabled is not None:
        config["telegram_signals_enabled"] = data.telegram_signals_enabled
    if data.telegram_trades_enabled is not None:
        config["telegram_trades_enabled"] = data.telegram_trades_enabled

    telegram.update_config(config)
    save_config(config)
    return {"success": True, "config": config}

class TelegramTestRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

@app.post("/api/telegram/test")
async def test_telegram_connection(req: Optional[TelegramTestRequest] = Body(None)):
    """Test Telegram connection and send immediate verification alert."""
    token = (req.bot_token.strip() if req and req.bot_token else None) or telegram.bot_token
    chat_id = (str(req.chat_id).strip() if req and req.chat_id else None) or telegram.chat_id
    
    if not token or not chat_id:
        return {"success": False, "message": "⚠️ Telegram Bot Token or Chat ID is missing."}
        
    temp_bot = TelegramNotifier(bot_token=token, chat_id=chat_id)
    try:
        res = await temp_bot.test_connection()
        return res
    finally:
        await temp_bot.close()

@app.get("/api/telegram/status")
async def get_telegram_status():
    """Get live status of Telegram bot integration."""
    return {
        "configured": bool(telegram.bot_token and telegram.chat_id),
        "enabled": telegram.enabled,
        "signals_enabled": telegram.signals_enabled,
        "trades_enabled": telegram.trades_enabled,
        "chat_id": telegram.chat_id
    }

class BroadcastSignalRequest(BaseModel):
    pair: str
    side: Optional[str] = "CALL"
    timeframe: Optional[str] = "1h"

@app.post("/api/telegram/broadcast-signal")
async def broadcast_telegram_signal(req: BroadcastSignalRequest):
    """Manually or AI-triggered broadcast of high-confidence Sure Call signal to Telegram."""
    pair = req.pair
    candles_task = coindcx.get_candles(pair, interval=req.timeframe or "1h", limit=50)
    ob_task = coindcx.get_orderbook(pair, depth=15)
    rate_task = coindcx.get_usdt_inr_rate()
    candles, ob, rate = await asyncio.gather(candles_task, ob_task, rate_task)
    
    if not candles:
        raise HTTPException(status_code=400, detail=f"Insufficient candles for {pair}")
        
    analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair)
    curr_price = float(candles[-1]["close"])
    score = analysis.get("score", 65)
    setup = analysis.get("trade_setup", {})
    direction = (req.side or "CALL").upper() if req.side else ("CALL" if score >= 0 else "PUT")
    
    sl = setup.get("stop_loss") or (curr_price * (0.985 if "CALL" in direction else 1.015))
    tp1 = setup.get("take_profit_1") or (curr_price * (1.020 if "CALL" in direction else 0.980))
    tp2 = curr_price * (1.038 if "CALL" in direction else 0.962)
    tp3 = curr_price * (1.060 if "CALL" in direction else 0.940)
    
    imbalance = ob.get("imbalance_pct", 0.0) if ob else 0.0
    reasons = [
        f"Multi-Factor Score: {score}/100",
        f"Orderbook Depth Imbalance: {imbalance:+.1f}%",
        f"Candle Formation: {analysis.get('candle_patterns', {}).get('pattern', 'Momentum Wave')}"
    ]
    
    await telegram.send_sure_call_signal(
        pair=pair,
        side=direction,
        current_price=curr_price,
        rate=rate,
        win_probability=max(80.0, min(97.0, 55.0 + abs(score) * 0.42)),
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        confluence_reasons=reasons,
        leverage=5,
        timeframe=req.timeframe or "1h"
    )
    return {"success": True, "message": f"Sure Call Signal for {pair} ({direction}) broadcast to Telegram!"}

# ==========================================================
# REST API: Markets & Market Data
# ==========================================================

@app.get("/api/markets")
async def get_markets(limit: Optional[int] = None):
    """Get active futures instruments with 24h ticker data (all 505+ instruments)."""
    pairs = await scanner.get_top_futures_pairs(limit=limit)
    return {"count": len(pairs), "markets": pairs}

# ==========================================================
# REST API: Auto-Pilot Trader & Self-Correcting Mistake Memory
# ==========================================================

@app.get("/api/autotrader/status")
async def get_autotrader_status():
    """Get auto-pilot trader status, learned lessons, and activity logs."""
    return auto_trader.get_status()

@app.post("/api/autotrader/toggle")
async def toggle_autotrader(enable: Optional[bool] = None):
    """Toggle autonomous AI auto-trading ON or OFF."""
    if enable is None:
        if auto_trader.is_running:
            auto_trader.stop()
        else:
            auto_trader.start()
    elif enable:
        auto_trader.start()
    else:
        auto_trader.stop()
    return auto_trader.get_status()

class AutoTraderConfigUpdate(BaseModel):
    min_score: Optional[int] = None
    max_open_positions: Optional[int] = None
    leverage: Optional[int] = None
    position_size_inr: Optional[float] = None
    position_size_usd: Optional[float] = None
    scan_interval_sec: Optional[int] = None
    live_trading_enabled: Optional[bool] = None

@app.post("/api/autotrader/config")
async def update_autotrader_config(cfg: AutoTraderConfigUpdate):
    """Update risk limits and parameters for auto-trader."""
    if cfg.min_score is not None:
        auto_trader.config["min_score"] = cfg.min_score
    if cfg.max_open_positions is not None:
        auto_trader.config["max_open_positions"] = cfg.max_open_positions
    if cfg.leverage is not None:
        auto_trader.config["leverage"] = cfg.leverage
    if cfg.position_size_inr is not None:
        auto_trader.config["position_size_inr"] = cfg.position_size_inr
    if cfg.position_size_usd is not None:
        auto_trader.config["position_size_usd"] = cfg.position_size_usd
    if cfg.scan_interval_sec is not None:
        auto_trader.config["scan_interval_sec"] = cfg.scan_interval_sec
    if cfg.live_trading_enabled is not None:
        auto_trader.config["live_trading_enabled"] = cfg.live_trading_enabled
    auto_trader.save_memory()
    return auto_trader.get_status()

@app.get("/api/autotrader/decide/{pair}")
async def autotrader_decide(pair: str, interval: str = "1h"):
    """Ask LLM to scan candles, orderbook, indicators, and past mistakes to formulate a trading decision."""
    decision = await auto_trader.scan_candle_and_decide(pair, interval=interval)
    return decision

@app.get("/api/scalp/candle-scan/{pair}")
async def get_scalp_candle_scan(pair: str, interval: str = "15m"):
    """Track live candle pattern, wick rejections, and quick scalp profit targets."""
    candles = await coindcx.get_candles(pair, interval=interval, limit=30)
    ob = await coindcx.get_orderbook(pair, depth=15)
    if not candles:
        raise HTTPException(status_code=400, detail="Insufficient candle data")
    candle_patterns = TechnicalAnalysis.analyze_candle_patterns(candles)
    analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair)
    return {
        "pair": pair,
        "interval": interval,
        "price": analysis.get("current_price"),
        "candle_patterns": candle_patterns,
        "trade_setup": analysis.get("trade_setup"),
        "quant_score": analysis.get("score"),
        "action": analysis.get("action")
    }

@app.get("/api/candles/{pair}")
async def get_candles(pair: str, interval: str = "1h", limit: int = 100):
    """Get OHLCV candlesticks for pair."""
    candles = await coindcx.get_candles(pair, interval=interval, limit=limit)
    return {"pair": pair, "interval": interval, "count": len(candles), "candles": candles}

@app.get("/api/orderbook/{pair}")
async def get_orderbook(pair: str, depth: int = 20):
    """Get order book depth and whale wall analysis with low latency."""
    ob_raw = await coindcx.get_orderbook(pair, depth=depth)
    last_price = 0.0
    if ob_raw.get("bids"):
        try:
            bids = sorted([float(p) for p in ob_raw["bids"].keys()], reverse=True)
            if bids:
                last_price = bids[0]
        except Exception:
            pass
    analysis = TechnicalAnalysis.analyze_orderbook(ob_raw, last_price)
    return {"pair": pair, "price": last_price, "orderbook": analysis}

@app.get("/api/analyze/{pair}")
async def analyze_pair(pair: str, interval: str = "15m"):
    """Run full quantitative multi-factor analysis on a pair with multi-timeframe 1h confluence."""
    candles_task = coindcx.get_candles(pair, interval=interval, limit=50)
    c1h_task = coindcx.get_candles(pair, interval="1h", limit=50)
    ob_task = coindcx.get_orderbook(pair, depth=20)
    candles, c1h, ob = await asyncio.gather(candles_task, c1h_task, ob_task)
    
    if not candles or len(candles) < 10:
        raise HTTPException(status_code=400, detail="Insufficient candle data from CoinDCX")

    c1h_valid = c1h if (isinstance(c1h, list) and len(c1h) >= 15) else None
    analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair, candles_1h=c1h_valid)
    
    # Update paper trading mark price if active
    if analysis.get("current_price"):
        paper.update_mark_price(pair, analysis["current_price"])
    return analysis

# ==========================================================
# REST API: Scanner & Top Coin Suggestions
# ==========================================================

@app.post("/api/scan")
async def trigger_scan(top_n: int = 30, interval: str = "15m"):
    """Trigger background or sync market scan across futures."""
    if not scanner.is_scanning:
        asyncio.create_task(scanner.run_full_scan(top_n=top_n, interval=interval))
    return {"message": "Scan started", "progress": scanner.scan_progress}

@app.get("/api/scan/results")
async def get_scan_results():
    """Retrieve the latest scanned results and filtered categories."""
    results = scanner.cached_scan_results
    
    # Categorize into high-conviction directional calls
    top_calls = [r for r in results if r.get("action") == "CALL (BUY)"]
    top_puts = [r for r in results if r.get("action") == "PUT (SELL)"]
    top_buys = [r for r in results if r.get("score", 0) >= 30]
    top_sells = [r for r in results if r.get("score", 0) <= -30]
    oversold = [r for r in results if r.get("rsi", 50) < 35]
    overbought = [r for r in results if r.get("rsi", 50) > 65]
    heavy_walls = [r for r in results if abs(r.get("orderbook", {}).get("imbalance_pct", 0)) > 20]

    return {
        "timestamp": scanner.last_scan_time,
        "is_scanning": scanner.is_scanning,
        "progress": scanner.scan_progress,
        "total": len(results),
        "results": results,
        "categories": {
            "top_calls": top_calls[:8],
            "top_puts": top_puts[:8],
            "top_longs": top_buys[:8],
            "top_shorts": top_sells[:8],
            "oversold_reversal": oversold[:5],
            "overbought_exhaustion": overbought[:5],
            "whale_imbalance": heavy_walls[:5]
        }
    }

# ==========================================================
# REST API: LLM Trading Intelligence & Streaming
# ==========================================================

@app.get("/api/llm/stream/{pair}")
async def stream_llm_analysis(pair: str, interval: str = "1h"):
    """Stream AI reasoning token-by-token directly to UI."""
    candles_task = coindcx.get_candles(pair, interval=interval, limit=80)
    ob_task = coindcx.get_orderbook(pair, depth=20)
    candles, ob = await asyncio.gather(candles_task, ob_task)

    if not candles:
        async def err_gen():
            yield "data: Error: Insufficient market data\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair)

    async def event_generator():
        async for chunk in llm.stream_analysis(analysis):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/llm/analyze/{pair}")
async def request_llm_analysis(pair: str, interval: str = "1h"):
    """Generate complete AI trade thesis for pair."""
    candles_task = coindcx.get_candles(pair, interval=interval, limit=80)
    ob_task = coindcx.get_orderbook(pair, depth=20)
    candles, ob = await asyncio.gather(candles_task, ob_task)

    if not candles:
        raise HTTPException(status_code=400, detail="Insufficient market data")

    analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair)
    thesis = await llm.generate_analysis(analysis)
    return {
        "pair": pair,
        "analysis": analysis,
        "thesis": thesis
    }

# ==========================================================
# REST API: Account, Orders & Trade Management
# ==========================================================

@app.get("/api/account")
async def get_account_summary():
    """Get active trading account info (Paper or Real CoinDCX INR Wallet)."""
    rate = await coindcx.get_usdt_inr_rate()
    paper.set_usdt_inr_rate(rate)
    paper_summary = paper.get_summary()

    is_live = bool(config.get("live_trading_enabled", False) and coindcx.api_key and coindcx.secret_key)
    inr_wallet = None
    user_profile = None
    live_positions = []
    live_trades = []

    if coindcx.api_key and coindcx.secret_key:
        try:
            inr_wallet = await coindcx.get_inr_wallet_summary()
            user_info_res = await coindcx.get_user_info()
            if user_info_res.get("success"):
                user_profile = {
                    "username": user_info_res.get("username"),
                    "email": user_info_res.get("email"),
                    "kyc_status": user_info_res.get("kyc_status"),
                    "coindcx_id": user_info_res.get("coindcx_id")
                }
            if is_live:
                # Strictly fetch only CURRENTLY RUNNING live positions
                live_positions = await coindcx.get_futures_positions(margin_currency="INR", only_active=True)
                live_trades = await coindcx.get_futures_trades(limit=30)
        except Exception as e:
            print(f"[Account] Live sync error: {e}")

    # STRICT ISOLATION:
    # If mode is LIVE: paper is None so paper positions/history NEVER mix into live account!
    # If mode is PAPER: inr_wallet is None so live balances NEVER mix into paper trading!
    return {
        "mode": "LIVE" if is_live else "PAPER",
        "currency": "INR",
        "currency_symbol": "₹",
        "usdt_inr_rate": rate,
        "paper": paper_summary if not is_live else None,
        "inr_wallet": inr_wallet if is_live else None,
        "user_profile": user_profile,
        "live_positions": live_positions if is_live else [],
        "live_trades": live_trades if is_live else [],
        "live_configured": bool(coindcx.api_key and coindcx.secret_key)
    }

class ApiTestRequest(BaseModel):
    coindcx_key: Optional[str] = None
    coindcx_secret: Optional[str] = None

@app.post("/api/coindcx/test")
async def test_coindcx_api(req: Optional[ApiTestRequest] = Body(None)):
    """Test CoinDCX API credentials, verify authentication, and return live profile & balance details."""
    key = (req.coindcx_key.strip() if req and req.coindcx_key else None) or coindcx.api_key
    secret = (req.coindcx_secret.strip() if req and req.coindcx_secret else None) or coindcx.secret_key

    if not key or not secret:
        return {
            "success": False,
            "authenticated": False,
            "message": "⚠️ CoinDCX API Key or Secret Key is missing.",
            "guide": "Please enter your CoinDCX API Key and Secret Key in settings."
        }

    # Temporary client instance if testing new uncommitted keys
    test_client = CoinDCXClient(api_key=key, secret_key=secret)
    try:
        result = await test_client.test_connection()
        return result
    finally:
        await test_client.close()

@app.get("/api/coindcx/profile")
async def get_coindcx_profile():
    """Fetch current user profile and live trading balance from CoinDCX."""
    if not coindcx.api_key or not coindcx.secret_key:
        return {"success": False, "authenticated": False, "message": "API credentials not configured."}
    return await coindcx.test_connection()

@app.get("/api/self-learning/status")
async def get_self_learning_status():
    """Get self-learning mistake memory, adaptive institutional strategies, and evolution logs."""
    return auto_trader.learning_engine.get_summary()

@app.post("/api/self-learning/synthesize")
async def synthesize_learning_strategies():
    """Trigger LLM synthesis across trade history and mistake rules."""
    history = paper.get_summary().get("trade_history", [])
    mistakes = auto_trader.learning_engine.state.get("learned_mistake_rules", [])
    
    prompt = (
        f"You are an Institutional Crypto Futures Quantitative Risk Architect. "
        f"Analyze these recent trade outcomes and mistake rules:\n"
        f"Recent Trades: {json.dumps(history[-8:], default=str)}\n"
        f"Learned Mistake Rules: {json.dumps(mistakes[:5], default=str)}\n"
        f"In 3 bullet points, summarize the top strategic adjustments to maximize win rate with trailing stop-loss."
    )
    synthesis_text = await llm.generate(prompt, max_tokens=150, temperature=0.3)
    return {"success": True, "synthesis": synthesis_text, "summary": auto_trader.learning_engine.get_summary()}

@app.get("/api/paper/positions")
async def get_paper_positions():
    """Get active paper trading positions."""
    return paper.get_summary().get("positions", [])

@app.get("/api/paper/history")
async def get_paper_history():
    """Get paper trading trade history."""
    return paper.get_summary().get("trade_history", [])

class OrderRequest(BaseModel):
    symbol: str
    side: str               # 'LONG' or 'SHORT' / 'BUY' or 'SELL'
    quantity: float
    price: Optional[float] = None
    leverage: int = 5
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    margin_currency: str = "INR"
    trailing_sl_enabled: bool = True
    trailing_offset_pct: Optional[float] = 1.0

@app.post("/api/order/paper")
@app.post("/api/order/execute")
async def execute_order(order: OrderRequest):
    """Execute futures order with leverage, SL, and TP. Dispatches to live CoinDCX INR wallet or paper engine."""
    rate = await coindcx.get_usdt_inr_rate()
    paper.set_usdt_inr_rate(rate)

    exec_price = order.price
    if not exec_price or exec_price <= 0:
        candles = await coindcx.get_candles(order.symbol, interval="1m", limit=2)
        exec_price = float(candles[-1]["close"]) if candles else 100.0

    is_live = bool(config.get("live_trading_enabled", False) and coindcx.api_key and coindcx.secret_key)
    
    if is_live:
        live_res = await coindcx.create_futures_order_with_confirmation(
            pair=order.symbol,
            side="buy" if order.side.upper() in ["LONG", "BUY"] else "sell",
            order_type="market" if not order.price else "limit",
            quantity=order.quantity,
            price=order.price,
            leverage=order.leverage,
            margin_currency=order.margin_currency or "INR"
        )
        if not live_res.get("success"):
            detail = f"{live_res.get('message')} Guide: {live_res.get('guide')}"
            raise HTTPException(status_code=400, detail=detail)
        
        # Broadcast Live Manual Trade to Telegram
        margin_inr = round((exec_price * order.quantity * rate) / order.leverage, 2)
        asyncio.create_task(telegram.send_trade_opened(
            pair=order.symbol,
            side="CALL" if order.side.upper() in ["LONG", "BUY"] else "PUT",
            price=exec_price,
            quantity=order.quantity,
            leverage=order.leverage,
            rate=rate,
            margin_inr=margin_inr,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            trailing_sl_enabled=order.trailing_sl_enabled,
            trailing_offset_pct=order.trailing_offset_pct or 1.0,
            strategy_name="Manual Scalp Entry",
            is_live=True,
            order_id=str(live_res.get("order_id", ""))
        ))
        return {"success": True, "mode": "LIVE", "message": live_res.get("message"), "order_id": live_res.get("order_id"), "response": live_res}

    res = paper.open_position(
        symbol=order.symbol,
        side=order.side,
        price=exec_price,
        quantity=order.quantity,
        leverage=order.leverage,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        rate=rate,
        trailing_sl_enabled=order.trailing_sl_enabled,
        trailing_offset_pct=order.trailing_offset_pct,
        margin_currency=order.margin_currency or "INR"
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])

    # Broadcast Paper Manual Trade to Telegram
    margin_inr = round((exec_price * order.quantity * rate) / order.leverage, 2)
    asyncio.create_task(telegram.send_trade_opened(
        pair=order.symbol,
        side="CALL" if order.side.upper() in ["LONG", "BUY"] else "PUT",
        price=exec_price,
        quantity=order.quantity,
        leverage=order.leverage,
        rate=rate,
        margin_inr=margin_inr,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        trailing_sl_enabled=order.trailing_sl_enabled,
        trailing_offset_pct=order.trailing_offset_pct or 1.0,
        strategy_name="Manual Paper Entry",
        is_live=False
    ))
    return res

@app.post("/api/order/close")
async def close_position(symbol: str = Query(...)):
    """Close active position (strictly live CoinDCX or paper, never mixed)."""
    rate = await coindcx.get_usdt_inr_rate()
    paper.set_usdt_inr_rate(rate)

    is_live = bool(config.get("live_trading_enabled", False) and coindcx.api_key and coindcx.secret_key)
    if is_live:
        try:
            positions = await coindcx.get_futures_positions(margin_currency="INR", only_active=True)
            pos = next((p for p in positions if p.get("symbol") == symbol or p.get("pair") == symbol), None)
            if pos:
                pos_qty = float(pos.get("quantity") or pos.get("active_pos") or 0)
                pos_side = str(pos.get("side", "")).lower()
                opp_side = "sell" if "buy" in pos_side or "long" in pos_side else "buy"
                if abs(pos_qty) > 0:
                    close_res = await coindcx.create_futures_order_with_confirmation(
                        pair=symbol,
                        side=opp_side,
                        order_type="market",
                        quantity=abs(pos_qty),
                        leverage=int(pos.get("leverage") or 5),
                        margin_currency="INR"
                    )
                    candles = await coindcx.get_candles(symbol, interval="1m", limit=2)
                    exit_price = float(candles[-1]["close"]) if candles else float(pos.get("mark_price") or pos.get("entry_price") or 0)
                    pnl_inr = float(pos.get("unrealized_pnl") or 0)
                    roi = float(pos.get("unrealized_pnl_pct") or 0)
                    pnl_usd = round(pnl_inr / rate, 2) if rate > 0 else 0
                    is_call = "LONG" in pos.get("side", "").upper()

                    if pnl_inr >= 0:
                        asyncio.create_task(telegram.send_target_hit(
                            pair=symbol,
                            side="CALL" if is_call else "PUT",
                            entry_price=pos.get("entry_price", 0.0),
                            exit_price=exit_price,
                            quantity=abs(pos_qty),
                            realized_pnl_inr=pnl_inr,
                            realized_pnl_usdt=pnl_usd,
                            roi_pct=roi,
                            target_level="Live Position Closed / Target Hit",
                            is_live=True
                        ))
                    else:
                        asyncio.create_task(telegram.send_stoploss_hit(
                            pair=symbol,
                            side="CALL" if is_call else "PUT",
                            entry_price=pos.get("entry_price", 0.0),
                            exit_price=exit_price,
                            realized_pnl_inr=pnl_inr,
                            realized_pnl_usdt=pnl_usd,
                            roi_pct=roi,
                            is_trailing=False,
                            is_live=True,
                            learned_lesson="Live market position closed."
                        ))
                    return {"success": True, "mode": "LIVE", "message": f"Live CoinDCX position for {symbol} closed.", "response": close_res}
            return {"success": False, "mode": "LIVE", "message": f"No active live position found for {symbol}."}
        except Exception as e:
            print(f"[Order] Error closing live position: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to close live position: {e}")

    # PAPER MODE ONLY:
    candles = await coindcx.get_candles(symbol, interval="1m", limit=2)
    exit_price = float(candles[-1]["close"]) if candles else None
    res = paper.close_position(symbol, exit_price=exit_price, reason="MANUAL_CLOSE", rate=rate)

    # Broadcast to Telegram if position was closed
    if isinstance(res, dict) and "closed_trade" in res:
        closed = res["closed_trade"]
        pnl = closed.get("realized_pnl", 0.0)
        pnl_usd = round(pnl / rate, 2)
        roi = closed.get("pnl_pct", 0.0)
        is_call = closed.get("side", "").upper() in ["BUY", "LONG"]
        if pnl >= 0:
            asyncio.create_task(telegram.send_target_hit(
                pair=symbol,
                side="CALL" if is_call else "PUT",
                entry_price=closed.get("entry_price", 0.0),
                exit_price=closed.get("exit_price", 0.0),
                quantity=closed.get("quantity", 0.0),
                realized_pnl_inr=pnl,
                realized_pnl_usdt=pnl_usd,
                roi_pct=roi,
                target_level="Manual Exit / Target Reached",
                is_live=False
            ))
        else:
            asyncio.create_task(telegram.send_stoploss_hit(
                pair=symbol,
                side="CALL" if is_call else "PUT",
                entry_price=closed.get("entry_price", 0.0),
                exit_price=closed.get("exit_price", 0.0),
                realized_pnl_inr=pnl,
                realized_pnl_usdt=pnl_usd,
                roi_pct=roi,
                is_trailing=False,
                is_live=False,
                learned_lesson="Manual close risk cutoff executed."
            ))
    return res

@app.post("/api/account/reset")
async def reset_paper_account():
    """Reset virtual INR balance to initial ₹1,000,000, clear all positions, history, and logs to 0."""
    paper_summary = paper.reset(1000000.0)
    auto_trader.reset_stats()
    return {
        "success": True,
        "message": "Entire account, trade history, active positions, and logs reset to 0 (Fresh Start).",
        "paper": paper_summary,
        "autotrader": auto_trader.get_status()
    }

@app.get("/api/markets/candidates")
async def get_market_candidates(limit: int = 25):
    """Get high liquidity and momentum mover candidate coins."""
    candidates = await scanner.get_high_liquidity_momentum_candidates(limit=limit)
    return {"count": len(candidates), "candidates": candidates}

# ==========================================================
# REST API: AI Copilot Conversational Chat & Calculations
# ==========================================================

class CopilotQuery(BaseModel):
    query: str
    pair: Optional[str] = "B-BTC_USDT"

@app.post("/api/copilot/chat")
async def copilot_chat(req: CopilotQuery):
    """Conversational question or calculation with AI copilot."""
    pair = req.pair or "B-BTC_USDT"
    candles_task = coindcx.get_candles(pair, interval="1h", limit=30)
    ob_task = coindcx.get_orderbook(pair, depth=15)
    candles, ob = await asyncio.gather(candles_task, ob_task)
    
    active_analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair) if candles else {}
    top_coins = scanner.cached_scan_results[:6] if scanner.cached_scan_results else ([active_analysis] if active_analysis else [])
    context = {
        "active_coin": active_analysis,
        "top_coins": top_coins,
        "account": paper.get_summary()
    }
    reply = await llm.chat_copilot(req.query, context)
    return {"query": req.query, "reply": reply, "pair": pair}

@app.get("/api/copilot/stream")
async def copilot_stream(query: str, pair: Optional[str] = "B-BTC_USDT"):
    """Stream AI Copilot tokens in real time."""
    candles_task = coindcx.get_candles(pair, interval="1h", limit=30)
    ob_task = coindcx.get_orderbook(pair, depth=15)
    candles, ob = await asyncio.gather(candles_task, ob_task)
    
    active_analysis = TechnicalAnalysis.full_coin_analysis(candles, ob, pair) if candles else {}
    top_coins = scanner.cached_scan_results[:6] if scanner.cached_scan_results else ([active_analysis] if active_analysis else [])
    context = {
        "active_coin": active_analysis,
        "top_coins": top_coins,
        "account": paper.get_summary()
    }

    async def event_generator():
        async for chunk in llm.stream_chat_copilot(query, context):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ==========================================================
# WebSocket: Real-Time High-Speed Price & PnL Broadcaster
# ==========================================================

@app.websocket("/ws/ticker/{pair}")
async def websocket_ticker(websocket: WebSocket, pair: str):
    await websocket.accept()
    try:
        while True:
            candles_task = coindcx.get_candles(pair, interval="1m", limit=3)
            ob_task = coindcx.get_orderbook(pair, depth=10)
            rate_task = coindcx.get_usdt_inr_rate()
            candles, ob, rate = await asyncio.gather(candles_task, ob_task, rate_task)

            if candles:
                last_price = float(candles[-1]["close"])
                paper.update_mark_price(pair, last_price, rate=rate)

                # Ultra-fast real-time pricing for ALL open positions!
                for pos_sym in list(paper.state["positions"].keys()):
                    if pos_sym != pair:
                        pos_price = await coindcx.get_latest_price(pos_sym)
                        if pos_price and pos_price > 0:
                            paper.update_mark_price(pos_sym, pos_price, rate=rate)

                ob_summary = TechnicalAnalysis.analyze_orderbook(ob, last_price)
                
                payload = {
                    "pair": pair,
                    "price": last_price,
                    "price_inr": round(last_price * rate, 2),
                    "usdt_inr_rate": rate,
                    "high": float(candles[-1]["high"]),
                    "low": float(candles[-1]["low"]),
                    "volume": float(candles[-1]["volume"]),
                    "imbalance_pct": ob_summary["imbalance_pct"],
                    "spread_bps": ob_summary["spread_bps"],
                    "currency": "INR",
                    "currency_symbol": "₹",
                    "account": paper.get_summary()
                }
                await websocket.send_text(json.dumps(payload))
            
            await asyncio.sleep(0.8)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Exception: {e}")

@app.get("/api/wallet/all-balances")
async def get_all_balances():
    """Fetch all available currency balances (INR, USDT, BTC, ETH, etc.) and trading currency options."""
    rate = await coindcx.get_usdt_inr_rate()
    paper.set_usdt_inr_rate(rate)

    is_live = bool(config.get("live_trading_enabled", False) and coindcx.api_key and coindcx.secret_key)
    
    if is_live and coindcx.api_key and coindcx.secret_key:
        try:
            live_wallet = await coindcx.get_all_currency_balances()
            inr_summary = await coindcx.get_inr_wallet_summary()
            if live_wallet and live_wallet.get("balances"):
                inr_avail = inr_summary.get("inr_available", 0.0)
                usdt_avail = inr_summary.get("usdt_available", 0.0)
                return {
                    "mode": "LIVE",
                    "trading_currencies": [
                        {"currency": "INR", "symbol": "₹", "available": inr_avail, "total": inr_summary.get("inr_balance", 0.0), "locked": inr_summary.get("inr_locked", 0.0)},
                        {"currency": "USDT", "symbol": "$", "available": usdt_avail, "total": inr_summary.get("usdt_balance", 0.0), "locked": 0.0}
                    ],
                    "balances": live_wallet["balances"],
                    "futures_wallet": inr_summary.get("futures_wallet", {}),
                    "spot_wallet": inr_summary.get("spot_wallet", {}),
                    "options_wallet": inr_summary.get("options_wallet", {}),
                    "total_portfolio_inr": live_wallet.get("total_portfolio_inr", 0.0),
                    "total_portfolio_usdt": live_wallet.get("total_portfolio_usdt", 0.0),
                    "usdt_inr_rate": rate
                }
        except Exception as e:
            print(f"[Wallet] Balances error: {e}")

    # Fallback / Virtual Paper Balances
    acc = paper.get_summary()
    free_inr = acc.get("free_margin", 1000000.0)
    free_usdt = round(free_inr / rate, 2)

    virtual_balances = [
        {"currency": "INR", "balance": free_inr, "locked": acc.get("used_margin", 0.0), "available": free_inr, "value_inr": free_inr, "value_usdt": round(free_inr / rate, 2)},
        {"currency": "USDT", "balance": free_usdt, "locked": 0.0, "available": free_usdt, "value_inr": free_inr, "value_usdt": free_usdt},
        {"currency": "BTC", "balance": 0.25, "locked": 0.0, "available": 0.25, "value_inr": round(0.25 * 67000 * rate, 2), "value_usdt": round(0.25 * 67000, 2)},
        {"currency": "ETH", "balance": 2.5, "locked": 0.0, "available": 2.5, "value_inr": round(2.5 * 2600 * rate, 2), "value_usdt": round(2.5 * 2600, 2)},
        {"currency": "SOL", "balance": 35.0, "locked": 0.0, "available": 35.0, "value_inr": round(35.0 * 180 * rate, 2), "value_usdt": round(35.0 * 180, 2)}
    ]
    total_val_inr = sum(b["value_inr"] for b in virtual_balances)

    return {
        "mode": "PAPER",
        "trading_currencies": [
            {"currency": "INR", "symbol": "₹", "available": free_inr},
            {"currency": "USDT", "symbol": "$", "available": free_usdt}
        ],
        "balances": virtual_balances,
        "total_portfolio_inr": round(total_val_inr, 2),
        "total_portfolio_usdt": round(total_val_inr / rate, 2),
        "usdt_inr_rate": rate
    }

@app.get("/api/account/live-pnl")
async def get_live_pnl():
    """Ultra-fast live PnL and account snapshot across all open positions."""
    rate = await coindcx.get_usdt_inr_rate()
    is_live = bool(config.get("live_trading_enabled", False) and coindcx.api_key and coindcx.secret_key)
    
    live_positions = []
    if is_live:
        try:
            live_positions = await coindcx.get_futures_positions(margin_currency="INR", only_active=True)
        except Exception:
            pass
        return {
            "success": True,
            "mode": "LIVE",
            "account": None, # Never mix paper account in live mode!
            "live_positions": live_positions,
            "rate": rate,
            "timestamp": time.time()
        }
    else:
        for pos_sym in list(paper.state["positions"].keys()):
            pos_price = await coindcx.get_latest_price(pos_sym)
            if pos_price and pos_price > 0:
                paper.update_mark_price(pos_sym, pos_price, rate=rate)
        return {
            "success": True,
            "mode": "PAPER",
            "account": paper.get_summary(),
            "live_positions": [], # Never mix live in paper mode!
            "rate": rate,
            "timestamp": time.time()
        }
