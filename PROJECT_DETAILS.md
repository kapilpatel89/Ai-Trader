# ⚡ CoinDCX AI Institutional Futures Trading Terminal
## Comprehensive System Specification & Technical Architecture Documentation

---

## 📑 Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [High-Level System Architecture](#2-high-level-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Futures Trading Mechanics & Features](#4-futures-trading-mechanics--features)
5. [Core Backend Modules](#5-core-backend-modules)
   - [5.1 FastAPI Main Service (`backend/main.py`)](#51-fastapi-main-service-backendmainpy)
   - [5.2 CoinDCX Derivatives Client (`backend/coindcx_client.py`)](#52-coindcx-derivatives-client-backendcoindcx_clientpy)
   - [5.3 Quantitative Analysis Engine (`backend/technical_analysis.py`)](#53-quantitative-analysis-engine-backendtechnical_analysispy)
   - [5.4 Multi-Coin Scanner (`backend/scanner.py`)](#54-multi-coin-scanner-backendscannerpy)
   - [5.5 Local GPU LLM Engine (`backend/llm_engine.py`)](#55-local-gpu-llm-engine-backendllm_enginepy)
   - [5.6 Paper Trading Simulation Engine (`backend/paper_engine.py`)](#56-paper-trading-simulation-engine-backendpaper_enginepy)
   - [5.7 Autonomous Auto-Trader & Mistake Memory (`backend/auto_trader.py`)](#57-autonomous-auto-trader--mistake-memory-backendauto_traderpy)
6. [Frontend UI/UX Architecture](#6-frontend-uiux-architecture)
7. [Data Storage & State Persistence](#7-data-storage--state-persistence)
8. [Installation, Environment & Execution Pipeline](#8-installation-environment--execution-pipeline)
9. [Future Roadmap & Potential Enhancements](#9-future-roadmap--potential-enhancements)

---

## 1. Executive Summary

The **CoinDCX AI Institutional Futures Trading Terminal** is an institutional-grade, low-latency cryptocurrency derivatives workstation and automated quantitative trading bot. It bridges **CoinDCX Derivatives API infrastructure**, a **Multi-Factor Quantitative Screener**, and a **Local GPU-Accelerated LLM (Large Language Model)** running 100% offline on local hardware.

The platform eliminates cloud AI latency, recurring subscription costs, and sensitive API key leakage by running inference locally via `llama.cpp` (Vulkan/CUDA/CPU) with GPU VRAM priority (specifically optimized for NVIDIA GPUs, including low-VRAM architectures like GT 730 2GB, GTX, and RTX series).

### Core Highlights:
- **500+ Active Perpetual Futures Contracts** tracked in real-time.
- **Microsecond-grade Level-2 Order Book Analysis** with Whale Wall clustering and Bid/Ask Imbalance tracking.
- **Quantitative Composite Scoring** (-100 to +100) combining RSI, EMA ribbon alignment, MACD, Bollinger Bands, and Volume Spikes.
- **Autonomous Auto-Pilot Trading** with **Self-Correcting Mistake Memory** (post-trade autopsies on losses to prevent repeating losing setups).
- **Paper & Live Trading Modes** with isolated leverage (1x to 20x), dynamic liquidation price modeling, automated Stop-Loss (SL) and Take-Profit (TP) triggers.
- **Dual-Theme Neumorphic UI** (Light mode default, Obsidian dark mode) powered by TradingView Lightweight Charts.

---

## 2. High-Level System Architecture

```mermaid
graph TD
    subgraph Market Data Ingestion (100% CoinDCX API Exclusively)
        A1[CoinDCX Derivatives API<br/>active_instruments, candles, L2 orderbook]
        A2[CoinDCX High-Speed Price Feed<br/>market_data/current_prices, exchange/ticker]
    end

    subgraph Backend Core Python 3.10+ / FastAPI
        B1[CoinDCXClient<br/>HMAC-SHA256 Auth & Live Quote Engine]
        B2[MarketScanner<br/>500+ Contracts Screener]
        B3[TechnicalAnalysis<br/>RSI, EMA, MACD, BB, ATR, Whale Walls]
        B4[PaperTradingEngine<br/>Margin, Leverage, SL/TP, Liquidation]
        B5[AutoTradingAgent<br/>Autonomous Loop & Mistake Memory]
        B6[LLMEngine<br/>llama-server Manager & Ground-Truth Sanitizer]
        B7[FastAPI HTTP & WebSocket Gateway<br/>REST APIs, 350ms WS Ticker, SSE Streams]
    end

    subgraph Local AI Inference
        C1[llama-server.exe<br/>Vulkan / GPU Acceleration -ngl 99]
        C2[Qwen 2.5 0.5B / 1.5B GGUF<br/>models/ directory]
    end

    subgraph Client Application Frontend
        D1[Modern Glassmorphism / Neumorphic UI]
        D2[TradingView Lightweight Candlestick Chart]
        D3[Order Book Microstructure Visualizer]
        D4[AI Copilot & Mistake Memory Drawer]
        D5[Order Execution & Risk Management Form]
    end

    subgraph Persistent Storage
        E1[(data/config.json)]
        E2[(data/paper_account.json)]
        E3[(data/ai_memory.json)]
    end

    A1 --> B1
    A2 --> B1
    B1 --> B2
    B1 --> B3
    B2 --> B5
    B3 --> B5
    B4 <--> B5
    B6 <--> C1
    C1 --> C2
    B5 <--> B6
    B7 <--> B1
    B7 <--> B2
    B7 <--> B3
    B7 <--> B4
    B7 <--> B5
    B7 <--> B6
    B7 <--> D1
    D1 <--> D2
    D1 <--> D3
    D1 <--> D4
    D1 <--> D5
    B4 <--> E2
    B5 <--> E3
    B7 <--> E1
```

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend Framework** | `FastAPI` (Python 3.10+) | High-throughput asynchronous REST API & WebSockets |
| **ASGI Server** | `Uvicorn` | Lightning-fast async server handling SSE & WS connections |
| **Networking & HTTP** | `aiohttp`, `requests` | Non-blocking asynchronous HTTP requests with connection pooling |
| **WebSockets** | `websockets` | Sub-second real-time price & PnL broadcast pipeline (~800ms) |
| **Numeric & Quant Math**| `numpy` | Vectorized calculations for RSI, EMAs, MACD, Bollinger Bands, ATR |
| **Local AI Runtime** | `llama.cpp` (`llama-server.exe`) | Standalone C++ Vulkan/GPU inference server with `-ngl 99` |
| **AI Models** | Qwen 2.5 0.5B / 1.5B Instruct GGUF | Compact, high-signal quantized reasoning engine |
| **Frontend UI** | Vanilla HTML5, CSS3, JavaScript (ES6+) | Zero-dependency, ultra-fast client with dual theme styling |
| **Chart Engine** | `TradingView Lightweight Charts v4.1.1` | High-FPS canvas candlestick rendering with dynamic overlays |
| **Audio Feedback** | Web Audio API | Synthetic acoustic notifications for order execution and AI triggers |
| **Persistence** | Local JSON Store (`data/`) | Atomic disk storage for accounts, active positions, and AI memory |

---

## 4. Futures Trading Mechanics & Features

The platform is purpose-built for cryptocurrency futures contracts (derivatives) rather than spot trading:

### 1. Isolated Leverage (1x to 20x)
- Dynamic margin calculation:
  $$\text{Required Margin} = \frac{\text{Notional Value}}{\text{Leverage}} = \frac{\text{Price} \times \text{Quantity}}{\text{Leverage}}$$
- Allows testing strategies with high capital efficiency while isolating liquidation risk to only the assigned margin.

### 2. Dual Directional Trading (LONG & SHORT)
- **Long Positions**: Profit when mark price rises above entry:
  $$\text{PnL}_{\text{Long}} = (\text{Mark Price} - \text{Entry Price}) \times \text{Quantity}$$
- **Short Positions**: Profit when mark price drops below entry:
  $$\text{PnL}_{\text{Short}} = (\text{Entry Price} - \text{Mark Price}) \times \text{Quantity}$$

### 3. Rigorous Liquidation Modeling
- The simulation engine computes precise liquidation prices assuming a standard ~90% margin threshold:
  $$\text{Liquidation Price}_{\text{Long}} = \text{Entry Price} \times \left(1.0 - \frac{0.9}{\text{Leverage}}\right)$$
  $$\text{Liquidation Price}_{\text{Short}} = \text{Entry Price} \times \left(1.0 + \frac{0.9}{\text{Leverage}}\right)$$
- If the mark price breaches liquidation, the position is automatically liquidated and recorded.

### 4. Automated Stop-Loss (SL) & Take-Profit (TP)
- In both Paper and Auto-Trader modes, every tick checks active positions against SL and TP thresholds.
- When an SL/TP price is crossed, the position closes automatically, realizes PnL, frees margin, and triggers post-trade learning.

### 5. Order Book Microstructure & Whale Walls
- Identifies institutional whale orders holding $>15\%$ of total side liquidity.
- Computes **Order Book Imbalance (-100% to +100%)**:
  $$\text{Imbalance} = \frac{\text{Total Bid Volume} - \text{Total Ask Volume}}{\text{Total Bid Volume} + \text{Total Ask Volume}} \times 100$$
- Computes **Spread in Basis Points (bps)**:
  $$\text{Spread (bps)} = \frac{\text{Best Ask} - \text{Best Bid}}{\text{Mark Price}} \times 10,000$$

---

## 5. Core Backend Modules

### 5.1 FastAPI Main Service (`backend/main.py`)
Serves as the master orchestrator. It manages the application lifecycle, launches background tasks, serves static UI assets, and exposes REST/WebSocket endpoints.

- **Lifespan Manager**: On startup, launches the local `llama-server.exe` in GPU memory, triggers a background scan of top 25 liquid pairs, and restarts the auto-trader if previously enabled. On shutdown, cleanly closes HTTP sessions while preserving the LLM in GPU memory for instant re-runs.
- **Key Endpoints**:
  - `GET /api/status`: System health, GPU LLM state, CoinDCX credentials status, scanner state.
  - `POST /api/settings`: Updates API keys, live/paper toggle, default leverage, and model selection.
  - `GET /api/markets`: Returns all 505+ active CoinDCX futures contracts.
  - `GET /api/candles/{pair}`: Multi-timeframe OHLCV candles (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`).
  - `GET /api/orderbook/{pair}`: Level-2 depth, whale walls, and imbalance percentage.
  - `GET /api/analyze/{pair}`: Comprehensive quantitative multi-factor analysis report.
  - `POST /api/scan` & `GET /api/scan/results`: Background market screener and categorized top picks.
  - `GET /api/llm/stream/{pair}`: Server-Sent Events (SSE) token-by-token AI trade thesis streaming.
  - `GET /api/account` & `POST /api/order/paper`: Portfolio management and order placement.
  - `POST /api/copilot/chat` & `GET /api/copilot/stream`: Interactive chat copilot with API ground-truth.
  - `GET /api/autotrader/status` & `POST /api/autotrader/toggle`: Auto-pilot controls.
  - `WS /ws/ticker/{pair}`: High-frequency (~800ms) WebSocket price and PnL streamer.

### 5.2 CoinDCX Derivatives Client (`backend/coindcx_client.py`)
Encapsulates all asynchronous networking exclusively with CoinDCX:
- **Authentication**: Generates standard HMAC-SHA256 signatures for private endpoints (`/exchange/v1/users/balances`, `/exchange/v1/derivatives/futures/positions`, `/exchange/v1/derivatives/futures/orders/create`).
- **100% Pure CoinDCX Data Source**:
  - Uses only CoinDCX endpoints (`public.coindcx.com` and `api.coindcx.com`) without any external third-party price discrepancies.
  - Handles multiplier prefix differences (e.g. `B-1000PEPE_USDT` $\rightarrow$ `B-PEPE_USDT`).
  - High-frequency current price mapping via `market_data/current_prices` ensuring real-time sub-second price parity.

### 5.3 Quantitative Analysis Engine (`backend/technical_analysis.py`)
Computes mathematical indicators using NumPy:
- **RSI (14)**: Wilder's smoothing algorithm with gain/loss separation.
- **EMAs (9, 21, 50, 200)**: Exponential moving average ribbon to identify Golden/Death trend alignments.
- **MACD (12, 26, 9)**: Fast/Slow EMA divergence and momentum histogram.
- **Bollinger Bands (20, 2.0)**: Upper, middle, lower bands, %B position, and Bandwidth volatility squeeze.
- **ATR (14)**: Average True Range for dynamic volatility-based Stop Loss sizing (`1.5 * ATR`).
- **Support & Resistance**: Pivot swing high/low clustering across historical window.
- **Composite Score (-100 to +100)**:
  - $+25$ / $-25$ for RSI oversold / overbought conditions.
  - $+30$ / $-30$ for EMA 9 > 21 > 50 trend alignment.
  - $+25$ / $-25$ for Order Book Imbalance $> 20\%$ dominance.
  - $+15$ / $-15$ for Volume Surge ($>1.5\times$ 20-period average).

### 5.4 Multi-Coin Scanner (`backend/scanner.py`)
- Analyzes all active futures contracts on CoinDCX.
- Employs an `asyncio.Semaphore(5)` to prevent HTTP 429 rate-limiting while scanning in parallel.
- Categorizes setups into actionable tabs:
  - **Top Picks**: Highest absolute composite scores.
  - **Long Breakouts**: Bullish trend alignment + volume surge + buy wall support.
  - **Short Breakdowns**: Bearish trend alignment + sell wall pressure.
  - **Oversold Reversals**: Extreme RSI oversold ($<35$) with bottom support.
  - **Whale Imbalance**: Severe order book skew ($>25\%$ bid/ask dominance).

### 5.5 Local GPU LLM Engine (`backend/llm_engine.py`)
- Manages `models/llama_bin/llama-server.exe` with `-ngl 99` to offload all neural network layers into GPU VRAM.
- Built-in **Ground-Truth Sanitization Layer**: Cross-checks LLM responses against verified CoinDCX API prices to prevent hallucinations (such as assigning Bitcoin's price to an altcoin).
- Provides deterministic rule-based fallback if the local model is starting up or under heavy load.

### 5.6 Paper Trading Simulation Engine (`backend/paper_engine.py`)
- Maintains virtual account balances ($10,000 USD default).
- Implements isolated margin accounting, leverage multipliers, mark-price updates, and auto-liquidation.
- Tracks real-time win rates, winning/losing trade counts, total trades, realized/unrealized PnL, and stores trade history records to `data/paper_account.json`.

### 5.7 Autonomous Auto-Trader & Mistake Memory (`backend/auto_trader.py`)
- Autonomous background loop continuously scanning top liquid pairs using fresh CoinDCX API quotes.
- Risk parameters: Max open positions (3 default), position size ($300 margin), leverage (5x).
- **Self-Correcting Mistake Memory**:
  - Whenever a trade exits at a loss (via Stop Loss or Liquidation), triggers `conduct_post_trade_autopsy()`.
  - Prompts local LLM to extract the exact mistake reason and formulate a strict risk rule.
  - Stores rules in `data/ai_memory.json` with a cooldown period (1800s default).
  - In subsequent scans, evaluates candidate setups against past mistakes and aborts entries that match failure patterns (e.g., buying into overbought RSI or heavy sell walls).

---

## 6. Frontend UI/UX Architecture

The frontend is built as a responsive, high-performance single-page application without third-party frameworks:

### 1. Dual-Theme Neumorphic / Glassmorphism Design
- **Light Theme (Default)**: Modern off-white / light slate neumorphic aesthetic with soft extruded shadows, crisp borders, and dark typography.
- **Dark Theme (Switchable)**: Deep obsidian glassmorphism (`#080c14`) with neon green (`#00ff87`), neon cyan (`#00f2fe`), and crimson red (`#ff3b57`) accents.

### 2. 3-Column Terminal Layout
- **Left Column**: Multi-Coin Screener with real-time search, filter tabs (Top Picks, Longs, Shorts, Oversold, Whales), and live 24h ticker updates.
- **Center Column**:
  - Pair Header with live mark price and composite score badge.
  - Multi-timeframe selector (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`) + **Fullscreen Chart View** (`⛶ Fullscreen` toggle).
  - Interactive Candlestick Chart (TradingView Lightweight Charts) with Entry, SL, and TP line overlays (anchored permanently to real-time bars on the right, eliminating left auto-scroll bugs).
  - AI Reasoning Agent panel with token-by-token streaming.
  - Level-2 Order Book depth visualizer and real-time Imbalance Gauge.
  - **Active Positions & Trade History Tabbed Workstation**:
    - **Active Positions Tab**: Real-time unrealized PnL, leverage badges, liquidation prices, and 1-click market close.
    - **Trade History Tab**: Profit/Loss counters ribbon (Wins count, Losses count, Win Rate %, Net Realized PnL), alongside timestamped trade logs with entry/exit/reason details.
- **Right Column**: Trade Management card with account equity, free margin, leverage slider, order form, and 1-click execution.

### 3. Slide-Out AI Copilot Drawer
- Quick 1-click prompt chips:
  - *Candle Scan & Decide*
  - *Whale Walls Analysis*
  - *Mistake Memory Review*
  - *Profit & Leverage Math*
- Real-time conversational interface with streaming tokens.

---

## 7. Data Storage & State Persistence

All state is persisted locally inside the `./data/` directory in human-readable JSON format:

```
e:\AI trading\data\
├── config.json          # User settings (API keys, live trading toggle, model selection)
├── paper_account.json   # Balance, equity, open positions, closed trade history
└── ai_memory.json       # Learned lessons, mistake rules, and agent activity logs
```

### Sample Memory Structure (`data/ai_memory.json`):
```json
{
  "config": {
    "enabled": true,
    "min_score": 45,
    "max_open_positions": 3,
    "leverage": 5,
    "position_size_usd": 300.0,
    "scan_interval_sec": 20
  },
  "memory": {
    "total_mistakes_avoided": 4,
    "learned_lessons": [
      {
        "id": "lesson_1792504480",
        "symbol": "B-TAO_USDT",
        "side": "SHORT",
        "condition": "Failure on B-TAO_USDT SHORT exit via STOP_LOSS_TRIGGERED",
        "reason": "Loss on B-TAO_USDT SHORT. Incurred loss shorting into oversold support.",
        "action": "REJECT_SHORT",
        "learned_from": "Realized Loss of $18.00"
      }
    ]
  }
}
```

---

## 8. Installation, Environment & Execution Pipeline

### Prerequisites
- Windows 10/11 (64-bit).
- Python 3.10+ installed and added to `PATH`.
- NVIDIA GPU with CUDA/Vulkan support (or CPU fallback).

### One-Click Launch (`start.bat`)
Running `start.bat` executes the following sequence:
1. Validates Python installation.
2. Checks and installs dependencies from `requirements.txt`.
3. Verifies local `llama-server.exe` Vulkan binary and `qwen2.5-0.5b-instruct-q4_k_m.gguf` in `./models/` (downloads automatically if missing via `download_llm.py`).
4. Reclaims port 8000 if previously occupied.
5. Launches FastAPI via Uvicorn on `http://127.0.0.1:8000`.
6. Automatically opens the default browser to the terminal.

---

## 9. Future Roadmap & Potential Enhancements

To expand this institutional workstation further, the following high-impact features are slated for future development:

### 1. Multi-Exchange Aggregation
- Integrate additional cryptocurrency derivatives exchanges (Binance Futures, Bybit, OKX, Delta Exchange India) using unified CCXT or direct WebSocket protocols.
- Cross-exchange funding rate arbitrage and cross-market liquidation heatmaps.

### 2. Native Exchange WebSockets (L2 Order Book Diff Stream)
- Upgrade from polling public endpoints to CoinDCX direct WebSocket streams (`wss://stream.coindcx.com`) for sub-10ms depth updates.

### 3. Trailing Stop-Loss & Dynamic Breakeven Management
- Automatically shift the Stop-Loss to Breakeven (Entry Price) once Take-Profit 1 ($+1.5\times$ risk) is achieved.
- Implement ATR-based trailing stops to maximize gains on parabolic runners.

### 4. Advanced Machine Learning Classifiers
- Train an auxiliary LightGBM or XGBoost classifier on 1-minute order flow, CVD (Cumulative Volume Delta), and candlestick fractal patterns to predict 5-minute continuation probabilities.

### 5. Portfolio Risk Budgeting & Kelly Criterion Sizing
- Dynamically size positions according to historical win rate and variance using fractional Kelly sizing:
  $$f^* = \frac{p(b + 1) - 1}{b}$$
- Set strict daily drawdown circuit breakers (e.g., auto-halt all trading if daily drawdown exceeds 4%).

### 6. External Webhook Alerts (Telegram & Discord)
- Instant push notifications for trade entries, Stop-Loss triggers, profit targets hit, and AI autopsy lessons.

### 7. Vectorized Backtesting Engine
- Comprehensive backtesting framework to simulate quantitative scoring rules against multi-year historical 1m/5m/1h OHLCV data with realistic slippage and fee modeling.

### 8. Docker & Headless Cloud Deployment
- Containerize the backend and local llama runtime into a single Docker compose stack for 24/7 cloud VPS deployment (AWS, GCP, RunPod).

---
*Generated for CoinDCX AI Institutional Futures Trading Terminal codebase.*
