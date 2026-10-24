/**
 * Main Application Controller - CoinDCX AI Institutional Futures Terminal
 */

class SoundEffects {
    constructor() {
        this.ctx = null;
    }

    init() {
        if (!this.ctx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) this.ctx = new AudioCtx();
        }
    }

    playChime(freq = 880, type = "sine", duration = 0.15) {
        try {
            this.init();
            if (!this.ctx) return;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
            gain.gain.setValueAtTime(0.05, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start();
            osc.stop(this.ctx.currentTime + duration);
        } catch (e) {}
    }

    playOrderSuccess() {
        this.playChime(587, "sine", 0.1);
        setTimeout(() => this.playChime(880, "sine", 0.2), 100);
    }

    playAiAlert() {
        this.playChime(659, "triangle", 0.15);
        setTimeout(() => this.playChime(987, "triangle", 0.25), 120);
    }
}

class TerminalApp {
    constructor() {
        this.currentPair = "B-BTC_USDT";
        this.currentInterval = "1h";
        this.currentAnalysis = null;
        this.currentPrice = 0.0;
        this.ws = null;
        this.sound = new SoundEffects();
        this.orderbookInterval = null;

        // Components
        this.chartManager = null;
        this.orderbookViz = null;
        this.scannerUI = null;

        // Order form & currency state
        this.orderSide = "BUY";
        this.leverage = 5;
        this.selectedMarginCurrency = "INR";
        this.availableMarginInr = 1000000.0;
        this.availableMarginUsdt = 10000.0;
        this.pnlHeartbeatInterval = null;
        this.walletBalancesCache = null;

        this.init();
    }

    async init() {
        this.initTheme();
        this.initChartWithRetry();

        this.orderbookViz = new OrderbookVisualizer();
        this.scannerUI = new MarketScannerUI((selectedPair, coinData) => this.switchPair(selectedPair, coinData));

        this.bindEvents();

        try { this.loadSystemStatus(); } catch (e) { console.warn(e); }
        try { this.loadAccountSummary(); } catch (e) { console.warn(e); }
        try { this.fetchWalletBalances(); } catch (e) { console.warn(e); }

        if (this.scannerUI) {
            this.scannerUI.loadScannedResults().catch(e => console.error(e));
        }

        this.switchPair(this.currentPair).catch(e => console.error(e));
        this.startLivePnlHeartbeat();
    }

    initTheme() {
        const savedTheme = localStorage.getItem("terminal_theme") || "light";
        this.applyTheme(savedTheme);
    }

    applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const icon = document.getElementById("theme_icon");
        const text = document.getElementById("theme_text");
        if (icon) icon.textContent = theme === "light" ? "☀️" : "🌙";
        if (text) text.textContent = theme === "light" ? "Light" : "Dark";

        if (this.chartManager) {
            this.chartManager.setTheme(theme);
        }
    }

    toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const newTheme = current === "light" ? "dark" : "light";
        localStorage.setItem("terminal_theme", newTheme);
        this.applyTheme(newTheme);
        this.sound.playChime(newTheme === "light" ? 659 : 523, "sine", 0.08);
    }

    initChartWithRetry() {
        if (typeof LightweightCharts !== "undefined") {
            this.chartManager = new ChartManager("tradingview_chart");
            const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
            this.chartManager.setTheme(currentTheme);
            if (this.currentPair) {
                this.chartManager.loadCandles(this.currentPair, this.currentInterval);
            }
        } else {
            setTimeout(() => this.initChartWithRetry(), 200);
        }
    }

    bindEvents() {
        // Theme Toggle Button
        const btnToggleTheme = document.getElementById("btn_toggle_theme");
        if (btnToggleTheme) {
            btnToggleTheme.addEventListener("click", () => this.toggleTheme());
        }

        // Fullscreen toggle button
        const btnFullscreen = document.getElementById("btn_chart_fullscreen");
        if (btnFullscreen) {
            btnFullscreen.addEventListener("click", () => {
                if (this.chartManager) {
                    const isFull = this.chartManager.toggleFullscreen();
                    btnFullscreen.textContent = isFull ? "✕ Exit Fullscreen" : "⛶ Fullscreen";
                }
            });
        }

        // Active Positions vs Trade History Tab Switching
        const tabActive = document.getElementById("tab_active_positions");
        const tabHistory = document.getElementById("tab_trade_history");
        if (tabActive) tabActive.addEventListener("click", () => this.switchPosTab("active"));
        if (tabHistory) tabHistory.addEventListener("click", () => this.switchPosTab("history"));

        // Full View Toggle for Active Positions & Trade History
        const btnPosFullview = document.getElementById("btn_toggle_positions_fullview");
        const posCard = document.getElementById("active_positions_card");
        if (btnPosFullview && posCard) {
            btnPosFullview.addEventListener("click", () => {
                const isFull = posCard.classList.toggle("fullscreen-positions");
                const icon = document.getElementById("fullview_pos_icon");
                const text = document.getElementById("fullview_pos_text");
                if (icon) icon.textContent = isFull ? "✕" : "⛶";
                if (text) text.textContent = isFull ? "Exit Full View" : "Full View";
            });
        }

        window.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                if (posCard && posCard.classList.contains("fullscreen-positions")) {
                    posCard.classList.remove("fullscreen-positions");
                    const icon = document.getElementById("fullview_pos_icon");
                    const text = document.getElementById("fullview_pos_text");
                    if (icon) icon.textContent = "⛶";
                    if (text) text.textContent = "Full View";
                }
            }
        });

        // Timeframe selector
        document.querySelectorAll(".tf-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".tf-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.currentInterval = btn.getAttribute("data-tf");
                if (this.chartManager) {
                    this.chartManager.loadCandles(this.currentPair, this.currentInterval);
                }
                this.fetchPairAnalysis(this.currentPair);
            });
        });

        // Side Toggle: BUY vs SELL
        const btnSideBuy = document.getElementById("btn_side_buy");
        const btnSideSell = document.getElementById("btn_side_sell");
        const submitOrderBtn = document.getElementById("btn_submit_order");

        if (btnSideBuy && btnSideSell) {
            btnSideBuy.addEventListener("click", () => {
                this.orderSide = "BUY";
                btnSideBuy.classList.add("active");
                btnSideSell.classList.remove("active");
                if (submitOrderBtn) {
                    submitOrderBtn.textContent = `⚡ Execute BUY (${this.leverage}x)`;
                    submitOrderBtn.style.background = "var(--gradient-buy)";
                }
            });

            btnSideSell.addEventListener("click", () => {
                this.orderSide = "SELL";
                btnSideSell.classList.add("active");
                btnSideBuy.classList.remove("active");
                if (submitOrderBtn) {
                    submitOrderBtn.textContent = `⚡ Execute SELL (${this.leverage}x)`;
                    submitOrderBtn.style.background = "var(--gradient-sell)";
                }
            });
        }

        // Leverage Slider
        const levSlider = document.getElementById("leverage_slider");
        const levBadge = document.getElementById("leverage_val");
        if (levSlider && levBadge) {
            levSlider.addEventListener("input", (e) => {
                this.leverage = parseInt(e.target.value);
                levBadge.textContent = `${this.leverage}x`;
                if (submitOrderBtn) {
                    submitOrderBtn.textContent = `⚡ Execute ${this.orderSide} (${this.leverage}x)`;
                }
                this.updateOrderMarginEstimate();
            });
        }

        // Live Order Margin Estimate inputs
        const orderQtyInput = document.getElementById("order_qty_input");
        const orderPriceInput = document.getElementById("order_price_input");
        if (orderQtyInput) orderQtyInput.addEventListener("input", () => this.updateOrderMarginEstimate());
        if (orderPriceInput) orderPriceInput.addEventListener("input", () => this.updateOrderMarginEstimate());

        // Order Submit Button
        if (submitOrderBtn) {
            submitOrderBtn.addEventListener("click", () => this.executeOrder());
        }

        // Margin Currency Selection (INR vs USDT)
        const btnCurrInr = document.getElementById("btn_curr_inr");
        const btnCurrUsdt = document.getElementById("btn_curr_usdt");
        if (btnCurrInr && btnCurrUsdt) {
            btnCurrInr.addEventListener("click", () => {
                this.setTradingCurrency("INR");
            });
            btnCurrUsdt.addEventListener("click", () => {
                this.setTradingCurrency("USDT");
            });
        }

        // Quick Sizing Percentage Chips (10%, 25%, 50%, 75%, MAX)
        document.querySelectorAll(".btn-chip[data-size-pct]").forEach(chip => {
            chip.addEventListener("click", () => {
                const pct = parseFloat(chip.getAttribute("data-size-pct"));
                this.applySizingPercentage(pct);
            });
        });

        // Quick Stop Loss Chips (-1%, -2%, -3%, -5%)
        document.querySelectorAll(".sl-chip[data-sl-pct]").forEach(chip => {
            chip.addEventListener("click", () => {
                const pct = parseFloat(chip.getAttribute("data-sl-pct"));
                this.applyQuickStopLoss(pct);
            });
        });

        // Quick Take Profit Chips (+1.5%, +3%, +5%, +10%)
        document.querySelectorAll(".tp-chip[data-tp-pct]").forEach(chip => {
            chip.addEventListener("click", () => {
                const pct = parseFloat(chip.getAttribute("data-tp-pct"));
                this.applyQuickTakeProfit(pct);
            });
        });

        // In-Profit Trailing Offset Pills (0.5%, 0.8%, 1.0%, 1.5%)
        document.querySelectorAll(".btn-offset-pill[data-offset]").forEach(pill => {
            pill.addEventListener("click", () => {
                document.querySelectorAll(".btn-offset-pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                const offsetVal = pill.getAttribute("data-offset");
                const hiddenInput = document.getElementById("order_trailing_offset");
                if (hiddenInput) hiddenInput.value = offsetVal;
            });
        });

        // All Balances Modal Open & Close
        const btnOpenBalances = document.getElementById("btn_open_all_balances");
        const balancesModal = document.getElementById("all_balances_modal");
        const closeBalancesModal = document.getElementById("close_balances_modal");

        if (btnOpenBalances && balancesModal) {
            btnOpenBalances.addEventListener("click", async () => {
                balancesModal.style.display = "flex";
                await this.fetchWalletBalances(true);
            });
        }
        if (closeBalancesModal && balancesModal) {
            closeBalancesModal.addEventListener("click", () => {
                balancesModal.style.display = "none";
            });
        }
        window.addEventListener("click", (e) => {
            if (e.target === balancesModal) {
                balancesModal.style.display = "none";
            }
        });

        // Reset paper account button - Complete Fresh Start
        const btnResetAcc = document.getElementById("btn_reset_paper");
        if (btnResetAcc) {
            btnResetAcc.addEventListener("click", async () => {
                if (confirm("Reset entire portfolio balance, trade history, open positions, and AI logs to 0 for a complete Fresh Start?")) {
                    await fetch("/api/account/reset", { method: "POST" });
                    await this.loadAccountSummary();
                    await this.fetchWalletBalances();
                    this.sound.playChime(587, "sine", 0.15);
                    alert("✓ Complete Reset Done: Portfolio balance reset to ₹10,00,000 with 0 open positions, 0 trades, and 0 PnL!");
                }
            });
        }

        // Fast Refresh button
        const btnFastRefresh = document.getElementById("btn_fast_refresh");
        if (btnFastRefresh) {
            btnFastRefresh.addEventListener("click", async () => {
                btnFastRefresh.classList.add("spinning");
                await Promise.all([
                    this.scannerUI ? this.scannerUI.loadTopMarkets() : Promise.resolve(),
                    this.fetchPairAnalysis(this.currentPair),
                    this.loadAccountSummary(),
                    this.fetchWalletBalances()
                ]);
                setTimeout(() => btnFastRefresh.classList.remove("spinning"), 500);
            });
        }

        // Trading Mode Badge Quick Switch
        const modeBadgeEl = document.getElementById("trading_mode_badge");
        if (modeBadgeEl) {
            modeBadgeEl.style.cursor = "pointer";
            modeBadgeEl.title = "Click to toggle between LIVE Real Trading and PAPER Simulation";
            modeBadgeEl.addEventListener("click", async () => {
                const currentIsLive = modeBadgeEl.classList.contains("mode-live") || modeBadgeEl.textContent.includes("LIVE");
                const targetMode = currentIsLive ? "PAPER SIMULATION" : "REAL COINDCX LIVE TRADING";
                if (confirm(`Switch trading mode to ${targetMode}?`)) {
                    try {
                        await fetch("/api/settings", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ live_trading_enabled: !currentIsLive })
                        });
                        await this.loadAccountSummary();
                    } catch (e) {
                        alert("Error toggling mode: " + e.message);
                    }
                }
            });
        }

        // Settings Modal
        const btnSettings = document.getElementById("btn_settings");
        const modalOverlay = document.getElementById("settings_modal");
        const closeModal = document.getElementById("close_settings_modal");
        const btnSaveSettings = document.getElementById("btn_save_settings");

        if (btnSettings && modalOverlay) {
            btnSettings.addEventListener("click", () => {
                modalOverlay.style.display = "flex";
            });
        }

        if (closeModal && modalOverlay) {
            closeModal.addEventListener("click", () => {
                modalOverlay.style.display = "none";
            });
        }

        if (btnSaveSettings) {
            btnSaveSettings.addEventListener("click", async () => {
                await this.saveSettings();
                if (modalOverlay) modalOverlay.style.display = "none";
            });
        }

        // Test API Key Button in Settings
        const btnTestApiKey = document.getElementById("btn_test_api_key");
        if (btnTestApiKey) {
            btnTestApiKey.addEventListener("click", () => this.testApiCredentials());
        }

        // Test Telegram Button in Settings
        const btnTestTelegram = document.getElementById("btn_test_telegram");
        if (btnTestTelegram) {
            btnTestTelegram.addEventListener("click", () => this.testTelegramConnection());
        }

        // Broadcast Sure Call to Telegram button
        const btnBroadcastTelegram = document.getElementById("btn_broadcast_telegram");
        if (btnBroadcastTelegram) {
            btnBroadcastTelegram.addEventListener("click", () => this.broadcastCurrentPairToTelegram());
        }

        // Telegram status pill click -> opens settings
        const telegramStatusPill = document.getElementById("telegram_status_pill");
        if (telegramStatusPill) {
            telegramStatusPill.addEventListener("click", () => {
                const modal = document.getElementById("settings_modal");
                if (modal) modal.style.display = "flex";
            });
        }

        window.addEventListener("click", (e) => {
            if (e.target === modalOverlay) {
                modalOverlay.style.display = "none";
            }
        });

        // Auto Trader toggle
        const btnToggleAuto = document.getElementById("btn_toggle_autopilot");
        if (btnToggleAuto) {
            btnToggleAuto.addEventListener("click", () => this.toggleAutoTrader());
        }

        // Ask AI button in Center Panel
        const btnAskAi = document.getElementById("btn_ask_ai");
        if (btnAskAi) {
            btnAskAi.addEventListener("click", () => this.runAiAnalysis(this.currentPair));
        }

        // Copilot Drawer controls
        const drawer = document.getElementById("copilot_side_drawer");
        const btnCloseDrawer = document.getElementById("btn_close_copilot_drawer");
        const btnOpenDrawer = document.getElementById("btn_open_copilot_drawer");
        const btnFloating = document.getElementById("btn_floating_copilot");

        const openDrawer = () => {
            if (drawer) drawer.classList.add("open");
            this.updateDrawerActivePair();
            this.loadSelfLearningStatus();
        };
        const closeDrawer = () => {
            if (drawer) drawer.classList.remove("open");
        };

        if (btnOpenDrawer) btnOpenDrawer.addEventListener("click", openDrawer);
        if (btnFloating) btnFloating.addEventListener("click", () => {
            if (drawer && drawer.classList.contains("open")) {
                closeDrawer();
            } else {
                openDrawer();
            }
        });
        if (btnCloseDrawer) btnCloseDrawer.addEventListener("click", closeDrawer);

        // Drawer Tabs: Chat vs Strategies vs Mistakes
        const tabChat = document.getElementById("tab_drawer_chat");
        const tabStrats = document.getElementById("tab_drawer_strategies");
        const tabMistakes = document.getElementById("tab_drawer_mistakes");
        const viewChat = document.getElementById("view_drawer_chat");
        const viewStrats = document.getElementById("view_drawer_strategies");
        const viewMistakes = document.getElementById("view_drawer_mistakes");

        const setDrawerTab = (activeTab, activeView) => {
            [tabChat, tabStrats, tabMistakes].forEach(t => {
                if (t) {
                    t.classList.remove("active");
                    t.style.background = "transparent";
                    t.style.color = "var(--text-dim)";
                }
            });
            [viewChat, viewStrats, viewMistakes].forEach(v => {
                if (v) v.style.display = "none";
            });

            if (activeTab) {
                activeTab.classList.add("active");
                activeTab.style.background = "var(--bg-card)";
                activeTab.style.color = "var(--text-main)";
            }
            if (activeView) {
                activeView.style.display = "flex";
            }
        };

        if (tabChat) tabChat.addEventListener("click", () => setDrawerTab(tabChat, viewChat));
        if (tabStrats) tabStrats.addEventListener("click", () => {
            setDrawerTab(tabStrats, viewStrats);
            this.loadSelfLearningStatus();
        });
        if (tabMistakes) tabMistakes.addEventListener("click", () => {
            setDrawerTab(tabMistakes, viewMistakes);
            this.loadSelfLearningStatus();
        });

        // AI Synthesize Strategies Button
        const btnSynthesize = document.getElementById("btn_synthesize_strategies");
        if (btnSynthesize) {
            btnSynthesize.addEventListener("click", () => this.synthesizeStrategies());
        }

        // Scan Candle & Decide button inside Drawer
        const btnScanCandle = document.getElementById("btn_drawer_scan_candle");
        if (btnScanCandle) {
            btnScanCandle.addEventListener("click", () => this.runDrawerCandleScan(this.currentPair));
        }

        // Quick AI Command Chips
        document.querySelectorAll(".quick-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const prompt = chip.getAttribute("data-prompt");
                if (drawer && !drawer.classList.contains("open")) {
                    openDrawer();
                }
                this.sendCopilotMessage(prompt);
            });
        });

        // Chat Input & Send Button
        const copilotInput = document.getElementById("copilot_input");
        const btnCopilotSend = document.getElementById("btn_copilot_send");

        if (copilotInput && btnCopilotSend) {
            btnCopilotSend.addEventListener("click", () => {
                const val = copilotInput.value.trim();
                if (val) {
                    this.sendCopilotMessage(val);
                    copilotInput.value = "";
                }
            });

            copilotInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    const val = copilotInput.value.trim();
                    if (val) {
                        this.sendCopilotMessage(val);
                        copilotInput.value = "";
                    }
                }
            });
        }
    }

    switchPosTab(tabName) {
        const tabActive = document.getElementById("tab_active_positions");
        const tabHistory = document.getElementById("tab_trade_history");
        const viewActive = document.getElementById("view_active_positions");
        const viewHistory = document.getElementById("view_trade_history");

        if (tabName === "history") {
            if (tabHistory) tabHistory.classList.add("active");
            if (tabActive) tabActive.classList.remove("active");
            if (viewHistory) viewHistory.style.display = "flex";
            if (viewActive) viewActive.style.display = "none";
        } else {
            if (tabActive) tabActive.classList.add("active");
            if (tabHistory) tabHistory.classList.remove("active");
            if (viewActive) viewActive.style.display = "flex";
            if (viewHistory) viewHistory.style.display = "none";
        }
    }

    updateDrawerActivePair() {
        const drawerActivePair = document.getElementById("drawer_active_pair");
        if (drawerActivePair) {
            drawerActivePair.textContent = this.currentPair.replace("B-", "").replace("_", "/");
        }
    }

    async switchPair(pair, coinData = null) {
        this.currentPair = pair;
        const cleanName = pair.replace("B-", "").replace("_", "/");

        const pairTitle = document.getElementById("active_pair_title");
        if (pairTitle) pairTitle.textContent = cleanName;

        this.updateDrawerActivePair();

        // 1. Instant optimistic update from coinData if available
        if (coinData) {
            const optPrice = coinData.current_price || coinData.price;
            if (optPrice && optPrice > 0) {
                this.currentPrice = optPrice;
                const priceLabel = document.getElementById("active_pair_price");
                if (priceLabel) {
                    priceLabel.textContent = `$${optPrice >= 1 ? optPrice.toFixed(2) : optPrice.toFixed(5)}`;
                }
                const rate = window.currentUsdtInrRate || 100.74;
                const inrPrice = optPrice * rate;
                const priceInrLabel = document.getElementById("active_pair_price_inr");
                if (priceInrLabel) {
                    priceInrLabel.textContent = `₹${inrPrice.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                }
                const priceInput = document.getElementById("order_price_input");
                if (priceInput) priceInput.value = optPrice;
                this.updateOrderMarginEstimate();
            }

            if (coinData.score !== undefined) {
                this.updateQuantScoreBadge(coinData);
            }
        }

        // 2. Connect WebSocket ticker
        this.connectWebSocket(pair);

        // 3. Fast order book polling
        this.startFastOrderbookPolling(pair);

        // 4. Load candles and analysis in parallel
        await Promise.all([
            this.chartManager ? this.chartManager.loadCandles(pair, this.currentInterval) : Promise.resolve(),
            this.fetchPairAnalysis(pair)
        ]);
    }

    startFastOrderbookPolling(pair) {
        if (this.orderbookInterval) {
            clearInterval(this.orderbookInterval);
        }
        const poll = async () => {
            if (this.currentPair !== pair) return;
            try {
                const resp = await fetch(`/api/orderbook/${pair}?depth=15`);
                if (resp.ok) {
                    const data = await resp.json();
                    if (this.orderbookViz && data.orderbook) {
                        this.orderbookViz.render(data.orderbook, data.price || this.currentPrice);
                    }
                }
            } catch (e) {}
        };
        poll();
        this.orderbookInterval = setInterval(poll, 1500);
    }

    async fetchPairAnalysis(pair) {
        try {
            const resp = await fetch(`/api/analyze/${pair}?interval=${this.currentInterval}`);
            if (!resp.ok) return;
            const data = await resp.json();
            this.currentAnalysis = data;
            this.currentPrice = data.current_price;

            const priceLabel = document.getElementById("active_pair_price");
            if (priceLabel && data.current_price > 0) {
                priceLabel.textContent = `$${data.current_price >= 1 ? data.current_price.toFixed(2) : data.current_price.toFixed(5)}`;
            }

            const rate = window.currentUsdtInrRate || 100.74;
            const inrPrice = data.current_price * rate;
            const priceInrLabel = document.getElementById("active_pair_price_inr");
            if (priceInrLabel) {
                priceInrLabel.textContent = `₹${inrPrice.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }
            this.updateOrderMarginEstimate();

            if (this.orderbookViz && data.orderbook) {
                this.orderbookViz.render(data.orderbook, data.current_price);
            }

            if (this.chartManager && data.trade_setup) {
                this.chartManager.setTradePlanLines(data.trade_setup, pair);
            }

            this.prefillOrderForm(data);
            this.updateQuantScoreBadge(data);

        } catch (e) {
            console.error("[App] Analysis fetch error:", e);
        }
    }

    updateQuantScoreBadge(data) {
        const scoreBadge = document.getElementById("quant_score_badge");
        const actionLabel = document.getElementById("quant_action_label");
        
        if (scoreBadge && actionLabel) {
            const score = data.score || 0;
            const action = data.action || "WAIT (NEUTRAL)";
            const rr = data.trade_setup?.risk_reward ? ` • R:R 1:${data.trade_setup.risk_reward}` : "";
            const macro = data.macro_trend ? (data.macro_trend.includes("BULLISH") ? " • 1h ↗" : data.macro_trend.includes("BEARISH") ? " • 1h ↘" : "") : "";
            
            scoreBadge.textContent = `Score: ${score >= 0 ? '+' : ''}${score}/100${macro}`;
            scoreBadge.style.color = score >= 0 ? "var(--bullish)" : "var(--bearish)";

            actionLabel.textContent = `${action}${rr}`;
            if (action.includes("BUY") || action.includes("CALL")) {
                actionLabel.className = "stat-value up";
                actionLabel.style.background = "rgba(16, 185, 129, 0.15)";
                actionLabel.style.padding = "2px 8px";
                actionLabel.style.borderRadius = "4px";
                actionLabel.style.border = "1px solid rgba(16, 185, 129, 0.4)";
                actionLabel.style.fontWeight = "800";
            } else if (action.includes("SELL") || action.includes("PUT")) {
                actionLabel.className = "stat-value down";
                actionLabel.style.background = "rgba(239, 68, 68, 0.15)";
                actionLabel.style.padding = "2px 8px";
                actionLabel.style.borderRadius = "4px";
                actionLabel.style.border = "1px solid rgba(239, 68, 68, 0.4)";
                actionLabel.style.fontWeight = "800";
            } else {
                actionLabel.className = "stat-value";
                actionLabel.style.background = "rgba(100, 116, 139, 0.15)";
                actionLabel.style.color = "var(--text-muted)";
                actionLabel.style.padding = "2px 8px";
                actionLabel.style.borderRadius = "4px";
                actionLabel.style.border = "1px solid rgba(100, 116, 139, 0.25)";
            }
        }
    }

    prefillOrderForm(data) {
        const setup = data.trade_setup;
        if (!setup) return;

        const entryInput = document.getElementById("order_price_input");
        const slInput = document.getElementById("order_sl_input");
        const tpInput = document.getElementById("order_tp_input");

        if (entryInput && !entryInput.value) entryInput.value = setup.entry || data.current_price;
        if (slInput && setup.stop_loss) slInput.value = setup.stop_loss;
        if (tpInput && setup.take_profit_1) tpInput.value = setup.take_profit_1;

        if (setup.side === "LONG") {
            const btnBuy = document.getElementById("btn_side_buy");
            if (btnBuy) btnBuy.click();
        } else if (setup.side === "SHORT") {
            const btnSell = document.getElementById("btn_side_sell");
            if (btnSell) btnSell.click();
        }
    }

    async runAiAnalysis(pair) {
        const aiContainer = document.getElementById("ai_reasoning_content");
        const aiStatusTag = document.getElementById("ai_status_tag");
        if (!aiContainer) return;

        this.sound.playAiAlert();
        aiContainer.innerHTML = `<div style="display:flex;align-items:center;gap:10px;color:var(--neon-amber);"><i class="pulse-dot amber"></i> Local GPU LLM is synthesizing orderbook walls & indicators...</div>`;

        if (aiStatusTag) {
            aiStatusTag.innerHTML = `⚡ AI Reasoning In Progress`;
        }

        try {
            const evtSource = new EventSource(`/api/llm/stream/${pair}?interval=${this.currentInterval}`);
            let fullText = "";

            evtSource.onmessage = (event) => {
                if (event.data === "[DONE]") {
                    evtSource.close();
                    if (aiStatusTag) aiStatusTag.innerHTML = `✓ AI Analysis Complete`;
                    return;
                }

                try {
                    const parsed = JSON.parse(event.data);
                    if (parsed.chunk) {
                        fullText += parsed.chunk;
                        aiContainer.innerHTML = this.renderMarkdown(fullText);
                        aiContainer.scrollTop = aiContainer.scrollHeight;
                    }
                } catch (err) {}
            };

            evtSource.onerror = async () => {
                evtSource.close();
                try {
                    const resp = await fetch(`/api/llm/analyze/${pair}?interval=${this.currentInterval}`, { method: "POST" });
                    const data = await resp.json();
                    if (data.thesis) {
                        aiContainer.innerHTML = this.renderMarkdown(data.thesis);
                    }
                    if (aiStatusTag) aiStatusTag.innerHTML = `✓ AI Analysis Complete`;
                } catch (e) {
                    aiContainer.innerHTML = `<div style="color:var(--bearish)">Error connecting to AI inference engine.</div>`;
                }
            };

        } catch (e) {
            console.error("[App] AI Analysis error:", e);
            aiContainer.innerHTML = `<div style="color:var(--bearish)">Error connecting to AI inference engine.</div>`;
        }
    }

    async runDrawerCandleScan(pair) {
        const messagesContainer = document.getElementById("copilot_messages");
        if (!messagesContainer) return;

        const drawer = document.getElementById("copilot_side_drawer");
        if (drawer && !drawer.classList.contains("open")) {
            drawer.classList.add("open");
        }

        const userBubble = document.createElement("div");
        userBubble.className = "chat-bubble user";
        userBubble.textContent = `🕯 Scan candles and formulate trading decision for ${pair}`;
        messagesContainer.appendChild(userBubble);

        const aiBubble = document.createElement("div");
        aiBubble.className = "chat-bubble ai";
        aiBubble.innerHTML = `<div style="display:flex;align-items:center;gap:8px;color:var(--neon-amber);"><i class="pulse-dot amber"></i> Local GPU LLM scanning candlestick price action, order book walls & mistake memory...</div>`;
        messagesContainer.appendChild(aiBubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        this.sound.playAiAlert();

        try {
            const resp = await fetch(`/api/autotrader/decide/${pair}?interval=${this.currentInterval}`);
            const data = await resp.json();
            
            const badgeColor = data.decision === 'BUY' ? 'var(--bullish)' : data.decision === 'SELL' ? 'var(--bearish)' : 'var(--text-muted)';

            let candleCard = "";
            if (data.candle_patterns) {
                const cp = data.candle_patterns;
                const cpColor = cp.is_green ? 'var(--bullish)' : 'var(--bearish)';
                candleCard = `
                    <div style="background:rgba(0,0,0,0.3);border:1px solid var(--border-subtle);border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                            <span style="font-weight:700;font-size:11px;color:${cpColor};">🕯 ${cp.pattern}</span>
                            <span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(0,240,255,0.15);color:var(--neon-cyan);font-weight:700;">${cp.scalp_signal}</span>
                        </div>
                        <div style="font-size:11px;color:var(--text-bright);line-height:1.3;margin-bottom:4px;">${cp.recommendation}</div>
                        <div style="display:flex;gap:10px;font-size:10px;font-family:var(--font-mono);color:var(--text-dim);">
                            <span>Body: <strong>${cp.body_pct}%</strong></span>
                            <span>Upper Wick: <strong>${cp.upper_wick_pct}%</strong></span>
                            <span>Lower Wick: <strong>${cp.lower_wick_pct}%</strong></span>
                        </div>
                    </div>
                `;
            }

            let html = `
                ${candleCard}
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;border-bottom:1px solid var(--border-subtle);padding-bottom:6px;">
                    <span style="font-weight:800;font-size:14px;color:${badgeColor};">
                        VERDICT: ${data.decision} (${data.confidence}% Conviction)
                    </span>
                    <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-dim);">${data.pair}</span>
                </div>
                <div style="font-size:12px;line-height:1.5;margin-bottom:10px;">
                    ${this.renderMarkdown(data.reasoning)}
                </div>
            `;

            if (data.trade_setup && (data.decision === 'BUY' || data.decision === 'SELL')) {
                html += `
                    <div style="margin-top:8px;padding:8px 12px;background:rgba(0,0,0,0.3);border-radius:6px;border:1px solid var(--border-subtle);display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:11px;font-family:var(--font-mono);color:var(--neon-cyan);">
                            Entry: $${data.trade_setup.entry || data.price} | SL: $${data.trade_setup.stop_loss} | TP: $${data.trade_setup.take_profit_1}
                        </span>
                        <button class="btn-ai-scan" style="font-size:10px;padding:4px 8px;" onclick="window.terminalApp.prefillOrderForm(${JSON.stringify(data).replace(/"/g, '&quot;')})">
                            ⚡ Apply to Order Form
                        </button>
                    </div>
                `;
            }

            aiBubble.innerHTML = html;
            this.sound.playChime(880, "sine", 0.12);
        } catch (e) {
            console.error("[App] Candle scan error:", e);
            aiBubble.innerHTML = `<span style="color:var(--bearish)">Error running candle scan on ${pair}.</span>`;
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    sendCopilotMessage(userText) {
        const messagesContainer = document.getElementById("copilot_messages");
        if (!messagesContainer) return;

        const userBubble = document.createElement("div");
        userBubble.className = "chat-bubble user";
        userBubble.textContent = userText;
        messagesContainer.appendChild(userBubble);

        const aiBubble = document.createElement("div");
        aiBubble.className = "chat-bubble ai";
        aiBubble.innerHTML = `<span style="color:var(--neon-amber)">Thinking & Calculating on Local GPU...</span>`;
        messagesContainer.appendChild(aiBubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        this.sound.playAiAlert();

        let fullText = "";
        const url = `/api/copilot/stream?query=${encodeURIComponent(userText)}&pair=${encodeURIComponent(this.currentPair)}`;
        const evtSource = new EventSource(url);

        evtSource.onmessage = (event) => {
            if (event.data === "[DONE]") {
                evtSource.close();
                this.sound.playChime(784, "sine", 0.1);
                return;
            }

            try {
                const parsed = JSON.parse(event.data);
                if (parsed.chunk) {
                    fullText += parsed.chunk;
                    aiBubble.innerHTML = this.renderMarkdown(fullText);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (err) {}
        };

        evtSource.onerror = async () => {
            evtSource.close();
            try {
                const resp = await fetch("/api/copilot/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ query: userText, pair: this.currentPair })
                });
                const data = await resp.json();
                if (data.reply) {
                    aiBubble.innerHTML = this.renderMarkdown(data.reply);
                }
            } catch (e) {
                aiBubble.innerHTML = `<span style="color:var(--bearish)">Error connecting to Copilot engine.</span>`;
            }
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        };
    }

    setTradingCurrency(curr) {
        this.selectedMarginCurrency = curr.toUpperCase();
        const btnInr = document.getElementById("btn_curr_inr");
        const btnUsdt = document.getElementById("btn_curr_usdt");
        const labelName = document.getElementById("selected_currency_name");
        const labelAvail = document.getElementById("selected_currency_avail");

        if (this.selectedMarginCurrency === "INR") {
            if (btnInr) btnInr.classList.add("active");
            if (btnUsdt) btnUsdt.classList.remove("active");
            if (labelName) labelName.textContent = "INR";
            if (labelAvail) labelAvail.textContent = `₹${this.availableMarginInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        } else {
            if (btnUsdt) btnUsdt.classList.add("active");
            if (btnInr) btnInr.classList.remove("active");
            if (labelName) labelName.textContent = "USDT";
            if (labelAvail) labelAvail.textContent = `$${this.availableMarginUsdt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        }
        this.updateOrderMarginEstimate();
    }

    applySizingPercentage(pct) {
        const qtyInput = document.getElementById("order_qty_input");
        const price = parseFloat(document.getElementById("order_price_input")?.value || this.currentPrice || 0);
        if (!qtyInput || price <= 0) return;

        const rate = window.currentUsdtInrRate || 100.74;
        const lev = this.leverage || 5;

        let marginAvail = this.selectedMarginCurrency === "INR" ? this.availableMarginInr : this.availableMarginUsdt;
        if (!marginAvail || marginAvail <= 0) {
            marginAvail = this.selectedMarginCurrency === "INR" ? 1000000 : 10000;
        }

        const marginAlloc = marginAvail * (pct / 100.0);
        let calculatedQty = 0.0;

        if (this.selectedMarginCurrency === "INR") {
            const notionalInr = marginAlloc * lev;
            const notionalUsdt = notionalInr / rate;
            calculatedQty = notionalUsdt / price;
        } else {
            const notionalUsdt = marginAlloc * lev;
            calculatedQty = notionalUsdt / price;
        }

        if (calculatedQty > 0) {
            const formatted = calculatedQty >= 100 ? calculatedQty.toFixed(1) : calculatedQty >= 1 ? calculatedQty.toFixed(3) : calculatedQty.toFixed(5);
            qtyInput.value = formatted;
            this.updateOrderMarginEstimate();
            this.sound.playChime(659, "sine", 0.05);
        }
    }

    applyQuickStopLoss(pct) {
        const slInput = document.getElementById("order_sl_input");
        const price = parseFloat(document.getElementById("order_price_input")?.value || this.currentPrice || 0);
        if (!slInput || price <= 0) return;

        let sl = 0.0;
        if (this.orderSide === "BUY" || this.orderSide === "LONG") {
            sl = price * (1.0 - (pct / 100.0));
        } else {
            sl = price * (1.0 + (pct / 100.0));
        }

        slInput.value = price >= 1 ? sl.toFixed(2) : sl.toFixed(5);
        this.sound.playChime(523, "sine", 0.05);
    }

    applyQuickTakeProfit(pct) {
        const tpInput = document.getElementById("order_tp_input");
        const price = parseFloat(document.getElementById("order_price_input")?.value || this.currentPrice || 0);
        if (!tpInput || price <= 0) return;

        let tp = 0.0;
        if (this.orderSide === "BUY" || this.orderSide === "LONG") {
            tp = price * (1.0 + (pct / 100.0));
        } else {
            tp = price * (1.0 - (pct / 100.0));
        }

        tpInput.value = price >= 1 ? tp.toFixed(2) : tp.toFixed(5);
        this.sound.playChime(784, "sine", 0.05);
    }

    async executeOrder() {
        const qtyInput = document.getElementById("order_qty_input");
        const priceInput = document.getElementById("order_price_input");
        const slInput = document.getElementById("order_sl_input");
        const tpInput = document.getElementById("order_tp_input");
        const trailingCheck = document.getElementById("order_trailing_sl_check");
        const trailingOffsetInput = document.getElementById("order_trailing_offset");

        const qty = parseFloat(qtyInput ? qtyInput.value : 0);
        if (!qty || qty <= 0) {
            alert("Please enter a valid order quantity.");
            return;
        }

        const price = parseFloat(priceInput ? priceInput.value : 0) || this.currentPrice;
        const sl = parseFloat(slInput ? slInput.value : 0) || null;
        const tp = parseFloat(tpInput ? tpInput.value : 0) || null;

        const payload = {
            symbol: this.currentPair,
            side: this.orderSide === "BUY" ? "LONG" : "SHORT",
            quantity: qty,
            price: price,
            leverage: this.leverage,
            stop_loss: sl,
            take_profit: tp,
            margin_currency: this.selectedMarginCurrency || "INR",
            trailing_sl_enabled: trailingCheck ? trailingCheck.checked : true,
            trailing_offset_pct: parseFloat(trailingOffsetInput ? trailingOffsetInput.value : 0.8) || 0.8
        };

        try {
            const resp = await fetch("/api/order/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();

            if (resp.status !== 200 || data.error) {
                alert(`Order Error: ${data.detail || data.error}`);
                return;
            }

            this.sound.playOrderSuccess();
            await this.loadAccountSummary();
            await this.fetchWalletBalances();

        } catch (e) {
            console.error("[App] Order execution error:", e);
            alert("Error placing order.");
        }
    }

    updateOrderMarginEstimate() {
        const estVal = document.getElementById("est_margin_val");
        if (!estVal) return;
        const qty = parseFloat(document.getElementById("order_qty_input")?.value || 0);
        const price = parseFloat(document.getElementById("order_price_input")?.value || this.currentPrice || 0);
        const lev = this.leverage || 5;
        const rate = window.currentUsdtInrRate || 100.74;

        if (qty > 0 && price > 0 && lev > 0) {
            if (this.selectedMarginCurrency === "USDT") {
                const marginUsdt = (price * qty) / lev;
                estVal.textContent = `$${marginUsdt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            } else {
                const notionalInr = price * qty * rate;
                const marginInr = notionalInr / lev;
                estVal.textContent = `₹${marginInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }
        } else {
            estVal.textContent = this.selectedMarginCurrency === "USDT" ? "$0.00" : "₹0.00";
        }
    }

    async fetchWalletBalances(showModal = false) {
        try {
            const resp = await fetch("/api/wallet/all-balances");
            if (!resp.ok) return;
            const data = await resp.json();
            this.walletBalancesCache = data;

            if (data.trading_currencies && (data.mode === this.currentTradingMode || !this.currentTradingMode)) {
                const inrCur = data.trading_currencies.find(c => c.currency === "INR");
                const usdtCur = data.trading_currencies.find(c => c.currency === "USDT");
                if (inrCur && inrCur.available !== undefined) this.availableMarginInr = inrCur.available;
                if (usdtCur && usdtCur.available !== undefined) this.availableMarginUsdt = usdtCur.available;
            }

            // Update Avail display in order card
            const availEl = document.getElementById("selected_currency_avail");
            if (availEl) {
                if (this.selectedMarginCurrency === "USDT") {
                    availEl.textContent = `$${this.availableMarginUsdt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                } else {
                    availEl.textContent = `₹${this.availableMarginInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                }
            }

            // If modal open, populate balances list
            const modalTotalInr = document.getElementById("modal_total_portfolio_inr");
            const modalTotalUsdt = document.getElementById("modal_total_portfolio_usdt");
            const listEl = document.getElementById("modal_balances_list");

            if (modalTotalInr && data.total_portfolio_inr !== undefined) {
                modalTotalInr.textContent = `₹${data.total_portfolio_inr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }
            if (modalTotalUsdt && data.total_portfolio_usdt !== undefined) {
                modalTotalUsdt.textContent = `$${data.total_portfolio_usdt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            }

            if (listEl && data.balances) {
                let html = "";
                
                // 1. Futures Wallet Summary Card
                if (data.futures_wallet && (data.futures_wallet.inr_balance > 0 || data.futures_wallet.inr_available > 0)) {
                    const fw = data.futures_wallet;
                    html += `
                        <div style="background:rgba(0, 255, 135, 0.08);border:1px solid rgba(0, 255, 135, 0.35);border-radius:8px;padding:12px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                <div style="font-weight:800;color:var(--neon-green);font-size:12px;display:flex;align-items:center;gap:6px;">
                                    <span>⚡ CoinDCX Derivatives Futures Wallet</span>
                                    <span style="font-size:9px;background:rgba(0,255,135,0.2);color:var(--neon-green);padding:1px 6px;border-radius:4px;font-weight:700;">LIVE ACTIVE MARGIN</span>
                                </div>
                                <span style="font-size:11px;color:#94a3b8;font-family:var(--font-mono);">INR Margin Account</span>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-family:var(--font-mono);font-size:12px;">
                                <div><span style="color:#94a3b8;font-size:10px;display:block;">TOTAL MARGIN</span><strong>₹${(fw.inr_balance || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></div>
                                <div><span style="color:var(--neon-green);font-size:10px;display:block;">FREE AVAILABLE</span><strong style="color:var(--neon-green)">₹${(fw.inr_available || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></div>
                                <div><span style="color:#f59e0b;font-size:10px;display:block;">LOCKED (IN TRADES)</span><strong style="color:#f59e0b">₹${(fw.inr_locked || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></div>
                            </div>
                        </div>
                    `;
                }

                // 2. Currency list
                html += data.balances.map(b => {
                    const isTradingCurr = ["INR", "USDT"].includes(b.currency);
                    const isSelected = (b.currency === this.selectedMarginCurrency);
                    const badge = b.wallet_badge || (b.is_trading_margin ? "FUTURES" : "SPOT");
                    const badgeColor = badge === "FUTURES" ? "var(--neon-green)" : "#94a3b8";
                    const badgeBg = badge === "FUTURES" ? "rgba(0,255,135,0.15)" : "rgba(148,163,184,0.15)";
                    
                    return `
                        <div class="balance-item-row" style="${isSelected ? 'border-color:var(--neon-cyan);box-shadow:0 0 10px rgba(0,240,255,0.2);' : ''}">
                            <div style="display:flex;align-items:center;gap:10px;">
                                <div style="width:34px;height:34px;border-radius:50%;background:rgba(0,240,255,0.12);color:var(--neon-cyan);font-weight:800;display:flex;align-items:center;justify-content:center;font-size:12px;border:1px solid rgba(0,240,255,0.3);">
                                    ${b.currency.slice(0, 3)}
                                </div>
                                <div>
                                    <div style="font-weight:700;font-size:13px;color:#f8fafc;display:flex;align-items:center;gap:6px;">
                                        ${b.label || b.currency}
                                        <span style="font-size:9.5px;padding:1px 5px;border-radius:4px;background:${badgeBg};color:${badgeColor};border:1px solid ${badgeColor};">${badge}</span>
                                    </div>
                                    <div style="font-size:11px;color:#94a3b8;font-family:var(--font-mono);">
                                        Avail: <strong>${b.available}</strong> ${b.locked > 0 ? `(Locked: ${b.locked})` : ''}
                                    </div>
                                </div>
                            </div>
                            <div style="text-align:right;display:flex;align-items:center;gap:12px;">
                                <div>
                                    <div style="font-size:13px;font-weight:700;color:var(--neon-green);font-family:var(--font-mono);">₹${(b.value_inr || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                                    <div style="font-size:10.5px;color:#64748b;font-family:var(--font-mono);">$${(b.value_usdt || 0).toFixed(2)}</div>
                                </div>
                                ${isTradingCurr ? `
                                    <button type="button" class="btn-chip" style="padding:5px 10px;font-size:11px;${isSelected ? 'background:var(--neon-cyan);color:#0b1120;font-weight:800;' : ''}" onclick="window.terminalApp.setTradingCurrency('${b.currency}');document.getElementById('all_balances_modal').style.display='none';">
                                        ${isSelected ? 'Active' : 'Use for Trade'}
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    `;
                }).join("");

                // 3. Options Wallet Segregation Note
                html += `
                    <div style="background:rgba(168, 85, 247, 0.08);border:1px solid rgba(168, 85, 247, 0.25);border-radius:8px;padding:9px 12px;margin-top:8px;">
                        <div style="font-weight:700;color:#c084fc;font-size:11.5px;display:flex;align-items:center;gap:6px;">
                            <span>🎯 CoinDCX Options Wallet (Segregated Derivatives Sub-Wallet)</span>
                        </div>
                        <div style="font-size:11px;color:#94a3b8;margin-top:3px;line-height:1.4;">
                            CoinDCX crypto options trading operates with a segregated sub-wallet to isolate margin risk. Funds can be transferred to/from Spot or Futures instantly inside the CoinDCX mobile app or Web Wallet Manager.
                        </div>
                    </div>
                `;

                listEl.innerHTML = html;
            }
        } catch (e) {
            console.error("[App] Fetch wallet balances error:", e);
        }
    }

    startLivePnlHeartbeat() {
        if (this.pnlHeartbeatInterval) clearInterval(this.pnlHeartbeatInterval);
        this.pnlHeartbeatInterval = setInterval(async () => {
            try {
                const resp = await fetch("/api/account/live-pnl");
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.mode === "LIVE") {
                        this.updateLivePnlTick("LIVE", data.live_positions || [], this.latestInrWallet);
                    } else if (data.account) {
                        const paperPositions = data.account.positions ? (Array.isArray(data.account.positions) ? data.account.positions : Object.values(data.account.positions)) : [];
                        this.updateLivePnlTick("PAPER", paperPositions, data.account);
                    }
                }
            } catch (e) {}
        }, 1200);
    }

    updateLivePnlTick(mode, positions, accountOrWallet) {
        const isLive = (mode === "LIVE");
        const rate = window.currentUsdtInrRate || 100.74;

        // 1. Check if positions structure changed (new/closed position or mode change)
        const posSig = `${mode}:${positions.map(p => (p.symbol || p.pair || '') + ':' + (p.side || '') + ':' + (p.quantity || 0)).join('|')}`;
        if (posSig !== this._lastPositionsSignature) {
            this._lastPositionsSignature = posSig;
            this.renderPositions(positions, mode);
        } else {
            // Smoothly update PnL numbers and prices without destroying DOM
            let totalPnl = 0;
            positions.forEach(pos => {
                const pnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl : ((pos.pnl || 0) * rate);
                const pnlPct = pos.unrealized_pnl_pct !== undefined ? pos.unrealized_pnl_pct : (pos.pnl_pct || 0);
                totalPnl += pnl;
                const sym = pos.symbol || pos.pair;
                const pnlEl = document.getElementById(`pos_pnl_${sym}`);
                const markEl = document.getElementById(`pos_mark_${sym}`);
                const isUp = pnl >= 0;
                if (pnlEl) {
                    pnlEl.className = isUp ? 'stat-value up' : 'stat-value down';
                    pnlEl.textContent = `${isUp ? '+' : ''}₹${pnl.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})} (${isUp ? '+' : ''}${pnlPct.toFixed(2)}%)`;
                }
                if (markEl && pos.mark_price) {
                    markEl.textContent = `$${pos.mark_price >= 1 ? pos.mark_price.toFixed(2) : pos.mark_price.toFixed(5)}`;
                }
            });
            const pnlSummary = document.getElementById("pos_pnl_summary");
            if (pnlSummary) {
                const prefix = totalPnl >= 0 ? "+" : "";
                pnlSummary.innerHTML = `Unrealized PnL: <strong class="${totalPnl >= 0 ? 'stat-value up' : 'stat-value down'}">${prefix}₹${totalPnl.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong>`;
            }
        }

        // 2. Update Header & Box Balances smoothly without re-rendering tabs
        if (isLive) {
            const liveBal = accountOrWallet ? (accountOrWallet.inr_balance || 0) : 0;
            const liveFree = accountOrWallet ? (accountOrWallet.inr_available || 0) : 0;
            const liveUsed = accountOrWallet ? (accountOrWallet.inr_locked || 0) : 0;
            const eqLabel = document.getElementById("nav_equity_val");
            const balLabel = document.getElementById("acc_balance");
            const freeLabel = document.getElementById("acc_free_margin");
            const usedLabel = document.getElementById("acc_used_margin");
            if (eqLabel) eqLabel.textContent = `₹${liveBal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (balLabel) balLabel.textContent = `₹${liveBal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (freeLabel) freeLabel.textContent = `₹${liveFree.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (usedLabel) usedLabel.textContent = `₹${liveUsed.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        } else if (accountOrWallet) {
            const p = accountOrWallet;
            const eqLabel = document.getElementById("nav_equity_val");
            const balLabel = document.getElementById("acc_balance");
            const freeLabel = document.getElementById("acc_free_margin");
            const usedLabel = document.getElementById("acc_used_margin");
            if (eqLabel && p.equity !== undefined) eqLabel.textContent = `₹${p.equity.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (balLabel && p.balance !== undefined) balLabel.textContent = `₹${p.balance.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (freeLabel && p.free_margin !== undefined) freeLabel.textContent = `₹${p.free_margin.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (usedLabel && p.used_margin !== undefined) usedLabel.textContent = `₹${p.used_margin.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

            if (p.free_margin !== undefined) {
                this.availableMarginInr = p.free_margin;
                this.availableMarginUsdt = Math.round((p.free_margin / rate) * 100.0) / 100.0 || 10000.0;
                const availEl = document.getElementById("selected_currency_avail");
                if (availEl) {
                    if (this.selectedMarginCurrency === "USDT") {
                        availEl.textContent = `$${this.availableMarginUsdt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                    } else {
                        availEl.textContent = `₹${this.availableMarginInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                    }
                }
            }

            if (p.trade_history && Array.isArray(p.trade_history)) {
                const histCount = p.trade_history.length;
                if (histCount !== this._lastPaperHistoryCount) {
                    this._lastPaperHistoryCount = histCount;
                    this.renderTradeHistory(p.trade_history, p, "PAPER");
                    const histBadge = document.getElementById("history_tab_badge");
                    if (histBadge) histBadge.textContent = `${histCount} Closed`;
                }
            }
        }
    }

    async closePosition(symbol) {
        try {
            await fetch(`/api/order/close?symbol=${symbol}`, { method: "POST" });
            this.sound.playChime(600, "sine", 0.1);
            await this.loadAccountSummary();
        } catch (e) {
            console.error("[App] Close position error:", e);
        }
    }

    async loadAccountSummary() {
        try {
            const resp = await fetch("/api/account");
            const data = await resp.json();
            if (data.usdt_inr_rate) {
                window.currentUsdtInrRate = data.usdt_inr_rate;
            }

            const isLive = (data.mode === "LIVE");
            const modeBadge = document.getElementById("trading_mode_badge");
            if (modeBadge) {
                if (isLive) {
                    modeBadge.className = "mode-badge mode-live";
                    modeBadge.textContent = "LIVE COINDCX (INR)";
                    modeBadge.style.background = "rgba(0, 255, 135, 0.15)";
                    modeBadge.style.color = "var(--neon-green)";
                    modeBadge.style.borderColor = "var(--neon-green)";
                } else {
                    modeBadge.className = "mode-badge mode-paper";
                    modeBadge.textContent = "PAPER TRADING (INR)";
                    modeBadge.style.background = "rgba(234, 179, 8, 0.15)";
                    modeBadge.style.color = "var(--neon-amber)";
                    modeBadge.style.borderColor = "var(--neon-amber)";
                }
            }

            // Live INR Futures Wallet sync in Nav - ONLY in LIVE mode
            const navInrItem = document.getElementById("nav_inr_wallet_item");
            const navInrVal = document.getElementById("nav_inr_wallet_val");
            if (isLive && data.inr_wallet && navInrItem && navInrVal) {
                this.latestInrWallet = data.inr_wallet;
                navInrItem.style.display = "flex";
                const avail = data.inr_wallet.inr_available !== undefined ? data.inr_wallet.inr_available : (data.inr_wallet.total_inr || 0);
                const total = data.inr_wallet.inr_balance !== undefined ? data.inr_wallet.inr_balance : avail;
                const locked = data.inr_wallet.inr_locked || 0;
                navInrVal.textContent = `₹${avail.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                navInrItem.title = `CoinDCX Derivatives Futures Wallet\nAvailable Margin: ₹${avail.toFixed(2)}\nLocked Margin: ₹${locked.toFixed(2)}\nTotal Margin: ₹${total.toFixed(2)}`;

                this.availableMarginInr = avail;
                if (data.inr_wallet.usdt_available !== undefined) {
                    this.availableMarginUsdt = data.inr_wallet.usdt_available;
                }
            } else if (!isLive) {
                // In Paper Mode: Strictly hide Live Wallet in top nav and use Paper Free Margin
                if (navInrItem) navInrItem.style.display = "none";
                const p = data.paper || {};
                const free = p.free_margin !== undefined ? p.free_margin : (p.balance !== undefined ? p.balance : 1000000.0);
                this.availableMarginInr = free;
                const rate = window.currentUsdtInrRate || 100.74;
                this.availableMarginUsdt = Math.round((free / rate) * 100.0) / 100.0 || 10000.0;
            }

            // User Profile in Nav
            const navUserItem = document.getElementById("nav_user_profile_item");
            const navUserVal = document.getElementById("nav_username_val");
            if (data.user_profile && navUserItem && navUserVal) {
                navUserItem.style.display = "flex";
                navUserVal.textContent = data.user_profile.username || "Verified";
            } else if (navUserItem) {
                navUserItem.style.display = "none";
            }

            if (data.live_trades) {
                this.latestLiveTrades = data.live_trades;
            }

            // Strictly apply account data without mixing live and paper
            this.applyAccountData(
                data.mode,
                data.live_positions || [],
                data.inr_wallet,
                data.paper,
                data.live_trades || []
            );

            try {
                const autoResp = await fetch("/api/autotrader/status");
                const autoData = await autoResp.json();
                this.applyAutotraderStatus(autoData);
            } catch (err) {}

        } catch (e) {
            console.error("[App] Account summary error:", e);
        }
    }

    applyAccountData(mode = "PAPER", livePositions = [], inrWallet = null, paperAccount = null, liveTrades = []) {
        if (typeof mode === "object" && mode !== null) {
            paperAccount = mode;
            mode = "PAPER";
        }
        const isLive = (mode === "LIVE");
        this.currentTradingMode = mode;

        // Header Metrics in INR
        const equityLabel = document.getElementById("nav_equity_val");
        const pnlLabel = document.getElementById("nav_pnl_val");
        const winrateLabel = document.getElementById("nav_winrate_val");

        // Balances Box in INR
        const balLabel = document.getElementById("acc_balance");
        const freeLabel = document.getElementById("acc_free_margin");
        const usedLabel = document.getElementById("acc_used_margin");

        // Update Position & History Tab Mode Chips & Badges without wiping DOM buttons
        const posModeTag = document.getElementById("pos_tab_mode_tag");
        const histModeTag = document.getElementById("hist_tab_mode_tag");
        const countBadge = document.getElementById("pos_count_badge");
        const histBadge = document.getElementById("history_tab_badge");

        const curCount = isLive ? (livePositions ? livePositions.length : 0) : (paperAccount?.positions ? (Array.isArray(paperAccount.positions) ? paperAccount.positions.length : Object.keys(paperAccount.positions).length) : 0);
        const histCount = isLive ? (liveTrades ? liveTrades.length : 0) : (paperAccount?.trade_history ? paperAccount.trade_history.length : 0);

        if (posModeTag) {
            posModeTag.textContent = isLive ? "LIVE" : "PAPER";
            posModeTag.style.background = isLive ? "rgba(16, 185, 129, 0.15)" : "rgba(217, 119, 6, 0.15)";
            posModeTag.style.color = isLive ? "var(--bullish)" : "var(--neon-amber)";
            posModeTag.style.border = `1px solid ${isLive ? 'var(--bullish)' : 'var(--neon-amber)'}`;
        }
        if (histModeTag) {
            histModeTag.textContent = isLive ? "LIVE" : "PAPER";
            histModeTag.style.background = isLive ? "rgba(16, 185, 129, 0.15)" : "rgba(217, 119, 6, 0.15)";
            histModeTag.style.color = isLive ? "var(--bullish)" : "var(--neon-amber)";
            histModeTag.style.border = `1px solid ${isLive ? 'var(--bullish)' : 'var(--neon-amber)'}`;
        }
        if (countBadge) countBadge.textContent = `${curCount} Open`;
        if (histBadge) histBadge.textContent = `${histCount} Closed`;

        // Update trading mode badge
        const modeBadge = document.getElementById("trading_mode_badge");
        if (modeBadge) {
            if (isLive) {
                modeBadge.className = "mode-badge mode-live";
                modeBadge.textContent = "LIVE COINDCX (INR)";
                modeBadge.style.background = "rgba(16, 185, 129, 0.15)";
                modeBadge.style.color = "var(--bullish)";
                modeBadge.style.borderColor = "var(--bullish)";
            } else {
                modeBadge.className = "mode-badge mode-paper";
                modeBadge.textContent = "PAPER TRADING (INR)";
                modeBadge.style.background = "rgba(217, 119, 6, 0.15)";
                modeBadge.style.color = "var(--neon-amber)";
                modeBadge.style.borderColor = "var(--neon-amber)";
            }
        }

        if (isLive) {
            // STRICT LIVE MODE: Only show live data from CoinDCX wallet and API
            const liveBal = inrWallet ? (inrWallet.inr_balance || 0) : 0;
            const liveFree = inrWallet ? (inrWallet.inr_available || 0) : 0;
            const liveUsed = inrWallet ? (inrWallet.inr_locked || 0) : 0;

            if (equityLabel) equityLabel.textContent = `₹${liveBal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (balLabel) balLabel.textContent = `₹${liveBal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (freeLabel) freeLabel.textContent = `₹${liveFree.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (usedLabel) usedLabel.textContent = `₹${liveUsed.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            this.availableMarginInr = liveFree;

            if (pnlLabel) {
                pnlLabel.textContent = "Live Margin";
                pnlLabel.className = "stat-value up";
            }
            if (winrateLabel) {
                winrateLabel.textContent = "Live CoinDCX";
            }

            const runningLive = Array.isArray(livePositions) ? livePositions : [];
            this.renderPositions(runningLive, "LIVE");
            this.renderTradeHistory(liveTrades || [], {}, "LIVE");
        } else {
            // STRICT PAPER MODE: Only show paper simulation data
            const p = paperAccount || {};
            const bal = p.balance !== undefined ? p.balance : 1000000.0;
            const free = p.free_margin !== undefined ? p.free_margin : bal;
            const used = p.used_margin !== undefined ? p.used_margin : 0.0;
            const eq = p.equity !== undefined ? p.equity : bal;

            if (equityLabel) equityLabel.textContent = `₹${eq.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (balLabel) balLabel.textContent = `₹${bal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (freeLabel) freeLabel.textContent = `₹${free.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            if (usedLabel) usedLabel.textContent = `₹${used.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            this.availableMarginInr = free;

            if (pnlLabel && p.total_pnl_pct !== undefined) {
                const prefix = p.total_pnl_pct >= 0 ? "+" : "";
                pnlLabel.textContent = `${prefix}${p.total_pnl_pct.toFixed(2)}%`;
                pnlLabel.className = p.total_pnl_pct >= 0 ? "stat-value up" : "stat-value down";
            }
            if (winrateLabel && p.win_rate !== undefined) {
                winrateLabel.textContent = `${p.win_rate.toFixed(1)}% (${p.total_trades || 0} trades)`;
            }

            const runningPaper = p.positions ? (Array.isArray(p.positions) ? p.positions : Object.values(p.positions)) : [];
            this.renderPositions(runningPaper, "PAPER");
            this.renderTradeHistory(p.trade_history || [], p, "PAPER");
        }

        this.updateOrderMarginEstimate();
        this.setTradingCurrency(this.selectedMarginCurrency || "INR");

        const btnResetPaper = document.getElementById("btn_reset_paper");
        if (btnResetPaper) {
            btnResetPaper.style.display = isLive ? "none" : "block";
        }
    }

    renderPositions(positions, mode = "PAPER") {
        const container = document.getElementById("positions_list");
        const countBadge = document.getElementById("pos_count_badge");
        const pnlSummary = document.getElementById("pos_pnl_summary");
        if (!container) return;

        const count = positions ? positions.length : 0;
        if (countBadge) countBadge.textContent = `${count} Open`;

        if (!positions || positions.length === 0) {
            container.innerHTML = `
                <div style="text-align:center;padding:24px 16px;color:var(--text-dim);font-size:12px;">
                    <div style="font-size:18px;margin-bottom:6px;">✨</div>
                    No active <strong>${mode === 'LIVE' ? 'Live CoinDCX' : 'Paper Simulation'}</strong> futures positions running right now.
                    <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">When a ${mode === 'LIVE' ? 'live' : 'paper'} trade is executed, it will show live tracking and trailing SL here.</div>
                </div>
            `;
            if (pnlSummary) pnlSummary.textContent = "Unrealized PnL: ₹0.00";
            return;
        }

        let totalPnl = 0;
        const rate = window.currentUsdtInrRate || 100.74;
        const isLive = (mode === "LIVE");

        const itemsHtml = positions.map(pos => {
            const pnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl : ((pos.pnl || 0) * rate);
            const pnlPct = pos.unrealized_pnl_pct !== undefined ? pos.unrealized_pnl_pct : (pos.pnl_pct || 0);
            totalPnl += pnl;
            const isUp = pnl >= 0;
            const sym = pos.symbol || pos.pair || "";
            const cleanSym = sym.replace("B-", "").replace("_", "/");
            const isCurrent = (sym === this.currentPair);
            const side = String(pos.side || (pos.active_pos > 0 ? "LONG" : "SHORT")).toUpperCase();
            const lev = pos.leverage || 5;
            const entryPrice = pos.entry_price || pos.avg_price || 0;
            const markPrice = pos.mark_price || pos.current_price || entryPrice;
            const marginVal = pos.margin || pos.margin_inr || pos.locked_margin || 0;

            let slBadge = "";
            if (pos.trailing_sl_active) {
                slBadge = `<span style="background:rgba(2,132,199,0.12);color:var(--neon-cyan);border:1px solid rgba(2,132,199,0.35);border-radius:4px;padding:2px 7px;font-size:10px;font-weight:700;">🎯 Trailing SL (${pos.trailing_offset_pct || 1.0}%)</span>`;
            } else if (pos.breakeven_activated) {
                slBadge = `<span style="background:rgba(16,185,129,0.12);color:var(--bullish);border:1px solid rgba(16,185,129,0.35);border-radius:4px;padding:2px 7px;font-size:10px;font-weight:700;">🛡️ Breakeven Locked</span>`;
            }

            const modeBadgeStyle = isLive 
                ? "background:rgba(16,185,129,0.12);color:var(--bullish);border:1px solid rgba(16,185,129,0.35);"
                : "background:rgba(217,119,6,0.12);color:var(--neon-amber);border:1px solid rgba(217,119,6,0.35);";

            return `
                <div class="position-item ${isCurrent ? 'active-pos-card' : ''}" style="cursor:pointer;${isCurrent ? 'border-color:var(--neon-cyan);box-shadow:0 0 10px rgba(2,132,199,0.25);' : ''}" onclick="window.terminalApp.switchPair('${sym}')" title="Click to view ${cleanSym} chart, order book and live data">
                    <div class="pos-top">
                        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                            <span class="coin-badge ${side === 'LONG' || side === 'BUY' ? 'badge-long' : 'badge-short'}">${side} ${lev}x</span>
                            <strong class="hist-sym-text" style="color:var(--text-main);font-size:14px;font-weight:800;">${cleanSym}</strong>
                            <span style="font-size:9.5px;padding:2px 6px;border-radius:4px;font-weight:700;${modeBadgeStyle}">${isLive ? 'LIVE' : 'PAPER'}</span>
                            ${slBadge}
                            <span style="font-size:10px;color:var(--neon-cyan);background:rgba(2,132,199,0.1);border:1px solid rgba(2,132,199,0.25);padding:2px 6px;border-radius:4px;font-weight:700;">🔍 View Chart</span>
                        </div>
                        <div class="pos-pnl ${isUp ? 'stat-value up' : 'stat-value down'}" id="pos_pnl_${sym}" style="font-size:14px;font-weight:800;">
                            ${isUp ? '+' : ''}₹${pnl.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})} (${isUp ? '+' : ''}${pnlPct.toFixed(2)}%)
                        </div>
                    </div>
                    <div class="pos-details">
                        <div class="pos-stat"><span class="pos-label">Entry:</span> <strong style="color:var(--text-main);font-weight:700;">$${typeof entryPrice === 'number' ? (entryPrice >= 1 ? entryPrice.toFixed(2) : entryPrice.toFixed(5)) : entryPrice}</strong></div>
                        <div class="pos-stat"><span class="pos-label">Mark:</span> <strong style="color:var(--text-main);font-weight:700;" id="pos_mark_${sym}">$${typeof markPrice === 'number' ? (markPrice >= 1 ? markPrice.toFixed(2) : markPrice.toFixed(5)) : markPrice}</strong></div>
                        <div class="pos-stat"><span class="pos-label">SL:</span> <span style="${pos.trailing_sl_active ? 'color:var(--neon-cyan);font-weight:700;' : (pos.breakeven_activated ? 'color:var(--neon-green);font-weight:700;' : '')}">$${pos.stop_loss || 'Auto'} ${pos.trailing_sl_active ? '🔒' : (pos.breakeven_activated ? '🛡️' : '')}</span></div>
                        <div class="pos-stat"><span class="pos-label">TP:</span> <span style="color:var(--neon-green);font-weight:700;">$${pos.take_profit || 'Trailing'}</span></div>
                        <div class="pos-stat"><span class="pos-label">Margin:</span> <strong style="color:var(--text-main);font-weight:700;">₹${(marginVal || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</strong></div>
                        <div class="pos-stat"><span class="pos-label">Liq:</span> <span style="color:var(--bearish);font-weight:700;">$${pos.liquidation_price ? (pos.liquidation_price >= 1 ? pos.liquidation_price.toFixed(2) : pos.liquidation_price.toFixed(4)) : 'N/A'}</span></div>
                    </div>
                    <button class="btn-close-pos" onclick="event.stopPropagation(); window.terminalApp.closePosition('${sym}')">Market Close (${isLive ? 'Live' : 'Paper'})</button>
                </div>
            `;
        }).join("");

        const posSpacerHtml = `<div class="positions-end-spacer" style="height:40px;min-height:40px;width:100%;flex-shrink:0;pointer-events:none;"></div>`;
        container.innerHTML = `<div class="positions-grid">${itemsHtml}</div>${posSpacerHtml}`;

        if (pnlSummary) {
            const prefix = totalPnl >= 0 ? "+" : "";
            pnlSummary.innerHTML = `Unrealized PnL: <strong class="${totalPnl >= 0 ? 'stat-value up' : 'stat-value down'}">${prefix}₹${totalPnl.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong>`;
        }
    }

    renderTradeHistory(history = [], summary = {}, mode = "PAPER") {
        const historyBadge = document.getElementById("history_tab_badge");
        const winsCount = document.getElementById("history_wins_count");
        const lossesCount = document.getElementById("history_losses_count");
        const winrateLabel = document.getElementById("history_winrate");
        const realizedPnl = document.getElementById("history_realized_pnl");
        const listContainer = document.getElementById("trade_history_list");
        const isLive = (mode === "LIVE");

        const count = history ? history.length : 0;
        if (historyBadge) historyBadge.textContent = `${count} ${isLive ? 'Fills' : 'Closed'}`;

        if (isLive) {
            // Live account trade executions from CoinDCX API
            if (winsCount) winsCount.textContent = count;
            if (lossesCount) lossesCount.textContent = "0";
            if (winrateLabel) winrateLabel.textContent = "Live Fills";
            if (realizedPnl) {
                realizedPnl.textContent = "Live Orders";
                realizedPnl.className = "stat-value up";
            }

            if (!listContainer) return;
            if (!history || history.length === 0) {
                listContainer.innerHTML = `<div style="text-align:center;padding:24px 16px;color:var(--text-dim);font-size:12px;">No live CoinDCX trade fills recorded yet</div>`;
                return;
            }

            const rate = window.currentUsdtInrRate || 100.74;
            const itemsHtml = history.map(t => {
                const sym = t.symbol || t.pair || "";
                const cleanSym = sym.replace("B-", "").replace("_", "/");
                const rawSide = String(t.raw_side || t.side || "BUY").toUpperCase();
                const isBuy = rawSide.includes("BUY") || rawSide === "LONG";
                const qty = t.quantity || 0;
                const price = t.price || t.entry_price || 0;
                const notionalUsd = t.notional_usd || (price * qty);
                const notionalInr = t.notional_inr || (notionalUsd * rate);
                const timeStr = t.close_time ? new Date(t.close_time * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : "";

                return `
                    <div class="history-item win" style="cursor:pointer;" onclick="window.terminalApp.switchPair('${sym}')" title="Click to view ${cleanSym}">
                        <div class="hist-top">
                            <div class="hist-sym-wrap">
                                <span class="coin-badge ${isBuy ? 'badge-long' : 'badge-short'}" style="font-size:10px;padding:2px 7px;font-weight:800;">${isBuy ? '▲ BUY' : '▼ SELL'}</span>
                                <span class="hist-sym-text" style="font-size:14px;font-weight:800;color:var(--text-main);">${cleanSym}</span>
                                <span style="font-size:9.5px;padding:2px 6px;border-radius:4px;background:rgba(16,185,129,0.12);color:var(--bullish);border:1px solid rgba(16,185,129,0.35);font-weight:700;">🟢 LIVE FILL</span>
                                <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:rgba(2,132,199,0.1);color:var(--neon-cyan);border:1px solid rgba(2,132,199,0.25);font-weight:700;">🔍 View Chart</span>
                            </div>
                            <div class="hist-pnl stat-value up" style="text-align:right;">
                                <div style="font-size:14px;font-weight:800;color:var(--bullish);">₹${notionalInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                                <div style="font-size:11px;font-family:var(--font-mono);color:var(--neon-cyan);">$${notionalUsd.toFixed(2)} (${qty} units)</div>
                            </div>
                        </div>
                        <div class="hist-details">
                            <div>Exec Price: <strong style="color:var(--text-main);font-weight:700;">$${price >= 1 ? price.toFixed(2) : price.toFixed(5)}</strong></div>
                            <div>Fee: <span style="color:var(--text-dim);font-family:var(--font-mono);">${t.fee || 0}</span></div>
                            <div>Time: <span style="color:var(--text-dim);">${timeStr}</span></div>
                        </div>
                    </div>
                `;
            }).join("");

            const spacerHtml = `<div class="trade-history-end-spacer" style="height:60px;min-height:60px;width:100%;flex-shrink:0;pointer-events:none;"></div>`;
            listContainer.innerHTML = itemsHtml + spacerHtml;
            return;
        }

        // Paper mode trade history
        let wins = 0;
        let losses = 0;
        let totalNet = summary.realized_pnl || 0;

        if (history) {
            history.forEach(t => {
                const pnl = t.realized_pnl !== undefined ? t.realized_pnl : (t.pnl !== undefined ? t.pnl : 0);
                if (pnl > 0) wins++;
                else if (pnl < 0) losses++;
            });
        }

        if (winsCount) winsCount.textContent = wins;
        if (lossesCount) lossesCount.textContent = losses;
        if (winrateLabel) {
            const wr = summary.win_rate !== undefined ? summary.win_rate : (count > 0 ? (wins / count * 100) : 0);
            winrateLabel.textContent = `${wr.toFixed(1)}%`;
        }
        if (realizedPnl) {
            const prefix = totalNet >= 0 ? "+" : "";
            realizedPnl.textContent = `${prefix}₹${totalNet.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            realizedPnl.className = totalNet >= 0 ? "stat-value up" : "stat-value down";
        }

        if (!listContainer) return;
        if (!history || history.length === 0) {
            listContainer.innerHTML = `<div style="text-align:center;padding:24px 16px;color:var(--text-dim);font-size:12px;">No closed paper trades yet</div>`;
            return;
        }

        const itemsHtml = history.map(t => {
            const pnl = t.realized_pnl !== undefined ? t.realized_pnl : (t.pnl !== undefined ? t.pnl : 0);
            const isWin = pnl >= 0;
            const pnlPct = t.pnl_pct !== undefined ? t.pnl_pct : 0;
            const sym = t.symbol || t.pair || "";
            const cleanSym = sym.replace("B-", "").replace("_", "/");
            const side = String(t.side || "LONG").toUpperCase();
            const lev = t.leverage || 5;
            const entry = typeof t.entry_price === "number" ? (t.entry_price >= 1 ? t.entry_price.toFixed(2) : t.entry_price.toFixed(5)) : (t.entry_price || "--");
            const exit = typeof t.exit_price === "number" ? (t.exit_price >= 1 ? t.exit_price.toFixed(2) : t.exit_price.toFixed(5)) : (t.exit_price || "--");
            const rawReason = String(t.reason || "CLOSED").toUpperCase();
            
            let prettyReason = rawReason.replace(/_/g, " ");
            let reasonBadgeStyle = "background:rgba(100, 116, 139, 0.12);color:var(--text-muted);border:1px solid rgba(100, 116, 139, 0.25);";

            if (rawReason.includes("MAX_LOSS_CAP")) {
                prettyReason = "🛡️ Hard Loss Capped (-2%)";
                reasonBadgeStyle = "background:rgba(239, 68, 68, 0.18);color:#ef4444;border:1px solid rgba(239, 68, 68, 0.5);font-weight:700;";
            } else if (rawReason.includes("STAGNATION")) {
                prettyReason = "⏱️ Stagnation Cut (45m)";
                reasonBadgeStyle = "background:rgba(217, 119, 6, 0.18);color:var(--neon-amber);border:1px solid rgba(217, 119, 6, 0.5);font-weight:700;";
            } else if (rawReason.includes("TRAILING")) {
                prettyReason = "🎯 Trailing SL Locked";
                reasonBadgeStyle = "background:rgba(2, 132, 199, 0.12);color:var(--neon-cyan);border:1px solid rgba(2, 132, 199, 0.35);";
            } else if (rawReason.includes("BREAKEVEN")) {
                prettyReason = "🛡️ Breakeven";
                reasonBadgeStyle = "background:rgba(16, 185, 129, 0.12);color:var(--bullish);border:1px solid rgba(16, 185, 129, 0.35);";
            } else if (rawReason.includes("TAKE_PROFIT")) {
                prettyReason = "⚡ Take Profit";
                reasonBadgeStyle = "background:rgba(16, 185, 129, 0.15);color:var(--bullish);border:1px solid rgba(16, 185, 129, 0.35);";
            } else if (rawReason.includes("QUICK_PROFIT")) {
                prettyReason = "🔒 Profit Protection";
                reasonBadgeStyle = "background:rgba(2, 132, 199, 0.12);color:var(--neon-cyan);border:1px solid rgba(2, 132, 199, 0.35);";
            } else if (rawReason.includes("STOP_LOSS")) {
                prettyReason = "🛑 Stop Loss";
                reasonBadgeStyle = "background:rgba(239, 68, 68, 0.12);color:var(--bearish);border:1px solid rgba(239, 68, 68, 0.35);";
            } else if (rawReason.includes("LIQUIDATED")) {
                prettyReason = "💀 Liquidated";
                reasonBadgeStyle = "background:rgba(239, 68, 68, 0.2);color:#ff3b57;border:1px solid #ff3b57;";
            }

            const timeStr = t.close_time ? new Date(t.close_time * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : "";
            const rate = window.currentUsdtInrRate || 100.74;
            const pnlUsdt = pnl / rate;

            return `
                <div class="history-item ${isWin ? 'win' : 'loss'}" style="cursor:pointer;" onclick="window.terminalApp.switchPair('${sym}')" title="Click to view ${cleanSym}">
                    <div class="hist-top">
                        <div class="hist-sym-wrap">
                            <span class="coin-badge ${side === 'LONG' || side === 'BUY' ? 'badge-long' : 'badge-short'}" style="font-size:10.5px;padding:3px 8px;font-weight:800;">${side === 'LONG' || side === 'BUY' ? '▲ LONG' : '▼ SHORT'} ${lev}x</span>
                            <span class="hist-sym-text" style="font-size:14px;font-weight:800;color:var(--text-main);">${cleanSym}</span>
                            <span style="font-size:9.5px;padding:2px 6px;border-radius:4px;background:rgba(217,119,6,0.12);color:var(--neon-amber);border:1px solid rgba(217,119,6,0.35);font-weight:700;">🟡 PAPER</span>
                            <span class="hist-reason-badge" style="${reasonBadgeStyle}">${prettyReason}</span>
                            <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:rgba(2,132,199,0.1);color:var(--neon-cyan);border:1px solid rgba(2,132,199,0.25);font-weight:700;">🔍 View Chart</span>
                        </div>
                        <div class="hist-pnl ${isWin ? 'stat-value up' : 'stat-value down'}" style="text-align:right;">
                            <div style="font-size:14.5px;font-weight:800;color:${isWin ? 'var(--bullish)' : 'var(--bearish)'};">${isWin ? '+' : ''}₹${pnl.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            <div style="font-size:11px;font-family:var(--font-mono);color:${isWin ? 'var(--bullish)' : 'var(--bearish)'};">${isWin ? '+' : ''}${pnlPct.toFixed(2)}% (${isWin ? '+' : ''}$${pnlUsdt.toFixed(2)})</div>
                        </div>
                    </div>
                    <div class="hist-details">
                        <div>Entry: <strong style="color:var(--text-main);font-weight:700;">$${entry}</strong></div>
                        <div>Exit: <strong style="color:var(--text-main);font-weight:700;">$${exit}</strong></div>
                        <div>Time: <span style="color:var(--text-dim);">${timeStr}</span></div>
                    </div>
                </div>
            `;
        }).join("");

        const spacerHtml = `<div class="trade-history-end-spacer" style="height:60px;min-height:60px;width:100%;flex-shrink:0;pointer-events:none;"></div>`;
        listContainer.innerHTML = itemsHtml + spacerHtml;
    }

    applyAutotraderStatus(status) {
        if (!status) return;
        const btnToggle = document.getElementById("btn_toggle_autopilot");
        const dot = document.getElementById("autopilot_dot");
        const txt = document.getElementById("autopilot_status_text");
        const drawerState = document.getElementById("drawer_autopilot_state");
        const mistakesAvoided = document.getElementById("drawer_mistakes_avoided_count");
        const lessonsCount = document.getElementById("drawer_lessons_count");
        const mistakeBadge = document.getElementById("drawer_mistake_badge");

        const isRunning = status.is_running || status.enabled;

        if (btnToggle) {
            if (isRunning) {
                btnToggle.classList.add("active");
            } else {
                btnToggle.classList.remove("active");
            }
        }

        if (dot) {
            dot.className = isRunning ? "pulse-dot green" : "pulse-dot amber";
        }

        if (txt) {
            txt.textContent = isRunning ? "Auto-Pilot: ACTIVE" : "Auto-Pilot: OFF";
        }

        if (drawerState) {
            drawerState.textContent = isRunning ? "ACTIVE" : "STANDBY";
            drawerState.style.color = isRunning ? "var(--bullish)" : "var(--text-muted)";
        }

        if (mistakesAvoided && status.mistakes_avoided !== undefined) {
            mistakesAvoided.textContent = status.mistakes_avoided;
        }

        if (lessonsCount && status.learned_lessons_count !== undefined) {
            lessonsCount.textContent = status.learned_lessons_count;
        }

        if (mistakeBadge && status.learned_lessons_count !== undefined) {
            mistakeBadge.textContent = `${status.learned_lessons_count} Lessons`;
        }

        if (status.learning_summary) {
            this.renderSelfLearning(status.learning_summary);
        }
    }

    async toggleAutoTrader() {
        try {
            const resp = await fetch("/api/autotrader/toggle", { method: "POST" });
            const data = await resp.json();
            this.applyAutotraderStatus(data);
            this.sound.playChime(660, "sine", 0.1);
        } catch (e) {
            console.error("[App] Toggle auto trader error:", e);
        }
    }

    async loadSystemStatus() {
        try {
            const resp = await fetch("/api/status");
            const data = await resp.json();

            const modelPill = document.getElementById("model_status_pill");
            if (modelPill && data.llm) {
                modelPill.innerHTML = data.llm.ready 
                    ? `<i class="pulse-dot"></i> GPU LLM Online (${data.llm.active_model})`
                    : `<i class="pulse-dot amber"></i> LLM Initializing...`;
            }

            const modelSelect = document.getElementById("cfg_model_select");
            if (modelSelect && data.llm && data.llm.available_models) {
                modelSelect.innerHTML = data.llm.available_models.map(m => {
                    const sel = m === data.llm.active_model ? "selected" : "";
                    return `<option value="${m}" ${sel}>${m}</option>`;
                }).join("");
            }

            const liveCheckbox = document.getElementById("cfg_live_mode");
            if (liveCheckbox && data.coindcx) {
                liveCheckbox.checked = data.coindcx.live_mode;
            }

            if (data.telegram) {
                const tgTokenInput = document.getElementById("cfg_telegram_bot_token");
                const tgChatInput = document.getElementById("cfg_telegram_chat_id");
                const tgEnabled = document.getElementById("cfg_telegram_enabled");
                const tgSignals = document.getElementById("cfg_telegram_signals");
                const tgTrades = document.getElementById("cfg_telegram_trades");
                const tgPill = document.getElementById("telegram_status_pill");

                if (tgChatInput && !tgChatInput.value) tgChatInput.value = data.telegram.chat_id || "";
                if (tgEnabled) tgEnabled.checked = data.telegram.enabled;
                if (tgSignals) tgSignals.checked = data.telegram.signals_enabled;
                if (tgTrades) tgTrades.checked = data.telegram.trades_enabled;

                if (tgPill) {
                    if (data.telegram.configured && data.telegram.enabled) {
                        tgPill.innerHTML = `<i class="pulse-dot" style="background:#0088cc;box-shadow:0 0 8px #0088cc;"></i> <span>✈️ Telegram Active</span>`;
                        tgPill.style.borderColor = "#0088cc";
                    } else {
                        tgPill.innerHTML = `<i class="pulse-dot amber"></i> <span>✈️ Telegram Setup</span>`;
                        tgPill.style.borderColor = "var(--border-subtle)";
                    }
                }
            }

        } catch (e) {
            console.error("[App] Status error:", e);
        }
    }

    async saveSettings() {
        const key = document.getElementById("cfg_coindcx_key")?.value?.trim() || "";
        const secret = document.getElementById("cfg_coindcx_secret")?.value?.trim() || "";
        const model = document.getElementById("cfg_model_select")?.value || "";
        const live = document.getElementById("cfg_live_mode")?.checked || false;

        const tgToken = document.getElementById("cfg_telegram_bot_token")?.value?.trim();
        const tgChat = document.getElementById("cfg_telegram_chat_id")?.value?.trim();
        const tgEnabled = document.getElementById("cfg_telegram_enabled")?.checked;
        const tgSignals = document.getElementById("cfg_telegram_signals")?.checked;
        const tgTrades = document.getElementById("cfg_telegram_trades")?.checked;

        const payload = {
            selected_model: model,
            live_trading_enabled: live
        };
        if (key) payload.coindcx_key = key;
        if (secret) payload.coindcx_secret = secret;
        if (tgToken) payload.telegram_bot_token = tgToken;
        if (tgChat) payload.telegram_chat_id = tgChat;
        if (tgEnabled !== undefined) payload.telegram_enabled = tgEnabled;
        if (tgSignals !== undefined) payload.telegram_signals_enabled = tgSignals;
        if (tgTrades !== undefined) payload.telegram_trades_enabled = tgTrades;

        try {
            await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            alert("Settings saved successfully!");
            this.loadSystemStatus();
            this.loadAccountSummary();
        } catch (e) {
            alert("Error saving settings.");
        }
    }

    async testApiCredentials() {
        const keyInput = document.getElementById("cfg_coindcx_key");
        const secretInput = document.getElementById("cfg_coindcx_secret");
        const feedback = document.getElementById("api_test_feedback");
        const statusEl = document.getElementById("api_test_status");
        const detailsEl = document.getElementById("api_test_details");
        const btn = document.getElementById("btn_test_api_key");

        const key = keyInput ? keyInput.value.trim() : "";
        const secret = secretInput ? secretInput.value.trim() : "";

        if (feedback) feedback.style.display = "block";
        if (statusEl) {
            statusEl.innerHTML = `<i class="pulse-dot amber"></i> Connecting to CoinDCX API server...`;
            statusEl.style.color = "var(--neon-amber)";
        }
        if (detailsEl) detailsEl.textContent = "Testing HMAC-SHA256 signature and querying user info...";
        if (btn) btn.disabled = true;

        try {
            const resp = await fetch("/api/coindcx/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ coindcx_key: key, coindcx_secret: secret })
            });
            const data = await resp.json();

            if (data.success && data.authenticated) {
                this.sound.playOrderSuccess();
                if (statusEl) {
                    statusEl.innerHTML = `✓ ${data.message}`;
                    statusEl.style.color = "var(--neon-green)";
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `
                        <div style="margin-bottom:3px;">👤 <strong>User:</strong> ${data.username} (${data.email || 'Verified'}) | KYC: ${data.kyc_status}</div>
                        <div style="margin-bottom:3px;">💰 <strong>Available INR for Trade:</strong> ₹${(data.inr_available || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
                        <div style="margin-bottom:3px;">💵 <strong>Available USDT:</strong> $${(data.usdt_available || 0).toFixed(2)} | Total Portfolio: ₹${(data.total_portfolio_inr || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
                        <div>📊 <strong>Open Positions:</strong> ${data.open_positions_count || 0}</div>
                    `;
                }
                this.loadAccountSummary();
            } else {
                this.sound.playChime(400, "sawtooth", 0.2);
                if (statusEl) {
                    statusEl.innerHTML = `❌ ${data.message || data.error || 'Authentication Failed'}`;
                    statusEl.style.color = "var(--bearish)";
                }
                if (detailsEl) {
                    detailsEl.textContent = data.guide || "Check your API key and secret.";
                }
            }
        } catch (e) {
            if (statusEl) {
                statusEl.innerHTML = `❌ Connection Error: ${e.message}`;
                statusEl.style.color = "var(--bearish)";
            }
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async testTelegramConnection() {
        const tokenInput = document.getElementById("cfg_telegram_bot_token");
        const chatInput = document.getElementById("cfg_telegram_chat_id");
        const feedback = document.getElementById("telegram_test_feedback");
        const statusEl = document.getElementById("telegram_test_status");
        const detailsEl = document.getElementById("telegram_test_details");
        const btn = document.getElementById("btn_test_telegram");

        const token = tokenInput ? tokenInput.value.trim() : "";
        const chatId = chatInput ? chatInput.value.trim() : "";

        if (feedback) feedback.style.display = "block";
        if (statusEl) {
            statusEl.innerHTML = `<i class="pulse-dot amber"></i> Contacting Telegram Bot API...`;
            statusEl.style.color = "var(--neon-amber)";
        }
        if (detailsEl) detailsEl.textContent = "Verifying bot token and sending instant alert to chat ID...";
        if (btn) btn.disabled = true;

        try {
            const resp = await fetch("/api/telegram/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bot_token: token, chat_id: chatId })
            });
            const data = await resp.json();

            if (data.success) {
                this.sound.playOrderSuccess();
                if (statusEl) {
                    statusEl.innerHTML = `✓ ${data.message}`;
                    statusEl.style.color = "var(--neon-green)";
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `
                        <div>🤖 <strong>Bot Name:</strong> @${data.bot_username || 'antigravitycode_bot'} (${data.bot_name || 'Agent_bot'})</div>
                        <div>📱 <strong>Chat ID:</strong> <code>${chatId || '621591854'}</code></div>
                        <div style="margin-top:4px;color:var(--neon-cyan);">✨ Verification test message received in your Telegram! All Sure Calls (Call/Put), Entry, SL, TP & Realized PnL alerts are live.</div>
                    `;
                }
                this.loadSystemStatus();
            } else {
                this.sound.playChime(400, "sawtooth", 0.2);
                if (statusEl) {
                    statusEl.innerHTML = `❌ ${data.message || data.error || 'Connection Failed'}`;
                    statusEl.style.color = "var(--bearish)";
                }
                if (detailsEl) {
                    detailsEl.textContent = data.guide || "Check your Telegram Bot Token and Chat ID.";
                }
            }
        } catch (e) {
            if (statusEl) {
                statusEl.innerHTML = `❌ Connection Error: ${e.message}`;
                statusEl.style.color = "var(--bearish)";
            }
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async broadcastCurrentPairToTelegram() {
        const btn = document.getElementById("btn_broadcast_telegram");
        const origText = btn ? btn.innerHTML : "";
        if (btn) {
            btn.innerHTML = `✈️ Broadcasting...`;
            btn.disabled = true;
        }

        try {
            const resp = await fetch("/api/telegram/broadcast-signal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    pair: this.currentPair,
                    timeframe: this.currentInterval
                })
            });
            const data = await resp.json();
            if (resp.ok && data.success) {
                this.sound.playAiAlert();
                if (btn) btn.innerHTML = `✓ Signal Sent!`;
                setTimeout(() => {
                    if (btn) {
                        btn.innerHTML = origText;
                        btn.disabled = false;
                    }
                }, 2500);
            } else {
                alert(data.detail || data.message || "Failed to broadcast signal.");
                if (btn) {
                    btn.innerHTML = origText;
                    btn.disabled = false;
                }
            }
        } catch (e) {
            alert(`Error broadcasting signal: ${e.message}`);
            if (btn) {
                btn.innerHTML = origText;
                btn.disabled = false;
            }
        }
    }

    async loadSelfLearningStatus() {
        try {
            const resp = await fetch("/api/self-learning/status");
            if (!resp.ok) return;
            const data = await resp.json();
            this.renderSelfLearning(data);
        } catch (e) {
            console.error("[App] Error loading self-learning status:", e);
        }
    }

    renderSelfLearning(summary) {
        if (!summary) return;
        const stratContainer = document.getElementById("strategies_list_container");
        const mistakeContainer = document.getElementById("mistakes_list_container");
        const adaptationsBadge = document.getElementById("drawer_lessons_count");
        const mistakesAvoidedBadge = document.getElementById("drawer_mistakes_avoided_count");

        if (adaptationsBadge && summary.total_adaptation_cycles !== undefined) {
            adaptationsBadge.textContent = summary.total_adaptation_cycles || summary.strategies?.length || 4;
        }
        if (mistakesAvoidedBadge && summary.total_mistakes_avoided !== undefined) {
            mistakesAvoidedBadge.textContent = summary.total_mistakes_avoided;
        }

        if (stratContainer && summary.strategies) {
            stratContainer.innerHTML = summary.strategies.map(s => {
                const wr = s.win_rate || 70;
                const pnl = s.total_profit_inr || 0;
                const isProfit = pnl >= 0;
                return `
                    <div style="background:rgba(0,0,0,0.3);border:1px solid var(--border-subtle);border-radius:6px;padding:8px 10px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                            <span style="font-weight:700;font-size:12px;color:var(--neon-cyan);">${s.name}</span>
                            <span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(0,255,135,0.15);color:var(--neon-green);font-weight:700;">${wr}% Win Rate</span>
                        </div>
                        <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px;line-height:1.3;">${s.description}</div>
                        <div style="display:flex;justify-content:space-between;font-size:10px;font-family:var(--font-mono);color:var(--text-muted);border-top:1px solid rgba(255,255,255,0.05);padding-top:4px;">
                            <span>Target R:R: <strong>${s.target_rr}x</strong></span>
                            <span>Trailing SL: <strong>${s.trailing_sl_offset_pct}%</strong></span>
                            <span>Profit: <strong style="color:${isProfit ? 'var(--neon-green)' : 'var(--bearish)'}">${isProfit ? '+' : ''}₹${pnl.toLocaleString('en-IN')}</strong></span>
                        </div>
                        ${s.adaptation_notes ? `<div style="font-size:9.5px;color:var(--neon-amber);margin-top:4px;font-style:italic;">⚡ ${s.adaptation_notes}</div>` : ''}
                    </div>
                `;
            }).join("");
        }

        if (mistakeContainer && summary.mistake_rules) {
            mistakeContainer.innerHTML = summary.mistake_rules.map(m => {
                return `
                    <div style="background:rgba(255,59,48,0.06);border:1px solid rgba(255,59,48,0.25);border-radius:6px;padding:8px 10px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
                            <span style="font-weight:700;font-size:11px;color:var(--bearish);">${m.pattern || m.id}</span>
                            <span style="font-size:10px;background:rgba(0,255,135,0.15);color:var(--neon-green);padding:2px 5px;border-radius:3px;font-weight:700;">🛡️ ${m.times_prevented || 0} Blocked</span>
                        </div>
                        <div style="font-size:11px;color:var(--text-bright);line-height:1.3;">${m.reason}</div>
                        <div style="font-size:10px;font-family:var(--font-mono);color:var(--text-dim);margin-top:4px;">Rule: ${m.condition || m.action}</div>
                    </div>
                `;
            }).join("");
        }
    }

    async synthesizeStrategies() {
        const btn = document.getElementById("btn_synthesize_strategies");
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i class="pulse-dot amber"></i> Synthesizing...`;
        }
        try {
            const resp = await fetch("/api/self-learning/synthesize", { method: "POST" });
            const data = await resp.json();
            if (data.summary) {
                this.renderSelfLearning(data.summary);
            }
            if (data.synthesis) {
                alert(`✓ AI Strategy Synthesis Complete:\n\n${data.synthesis}`);
            }
            this.sound.playOrderSuccess();
        } catch (e) {
            alert("Error running strategy synthesis.");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `⚡ AI Synthesize`;
            }
        }
    }

    connectWebSocket(pair) {
        if (this.ws) {
            try { this.ws.close(); } catch (e) {}
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/ticker/${pair}`;
        
        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.pair !== this.currentPair) return;

                    if (data.price) {
                        this.currentPrice = data.price;
                        const priceLabel = document.getElementById("active_pair_price");
                        if (priceLabel) {
                            priceLabel.textContent = `$${data.price >= 1 ? data.price.toFixed(2) : data.price.toFixed(5)}`;
                        }

                        if (data.usdt_inr_rate) {
                            window.currentUsdtInrRate = data.usdt_inr_rate;
                        }
                        const rate = data.usdt_inr_rate || window.currentUsdtInrRate || 100.74;
                        const priceInr = data.price_inr || (data.price * rate);
                        const priceInrLabel = document.getElementById("active_pair_price_inr");
                        if (priceInrLabel) {
                            priceInrLabel.textContent = `₹${priceInr.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                        }

                        this.updateOrderMarginEstimate();

                        if (this.chartManager) {
                            this.chartManager.updateTick(data.price);
                        }
                    }

                    if (this.orderbookViz && (data.imbalance_pct !== undefined || data.spread_bps !== undefined)) {
                        this.orderbookViz.updateQuickStats(data.imbalance_pct, data.spread_bps);
                    }

                    if (data.account && this.currentTradingMode !== "LIVE") {
                        const paperPositions = data.account.positions ? (Array.isArray(data.account.positions) ? data.account.positions : Object.values(data.account.positions)) : [];
                        this.updateLivePnlTick("PAPER", paperPositions, data.account);
                    }

                } catch (err) {}
            };

            this.ws.onerror = () => {};
            this.ws.onclose = () => {};

        } catch (e) {
            console.warn("[App] WebSocket connect error:", e);
        }
    }

    renderMarkdown(text) {
        if (!text) return "";
        let clean = text.trim();
        clean = clean.replace(/^```[a-z0-9_-]*\s*\n?/i, "").replace(/\n?```\s*$/i, "");

        // Headings
        clean = clean.replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px;font-size:13px;color:var(--text-bright);">$1</h4>');
        clean = clean.replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 6px;font-size:14px;color:var(--text-bright);">$1</h3>');
        clean = clean.replace(/^# (.*$)/gim, '<h2 style="margin:12px 0 8px;font-size:15px;color:var(--text-bright);">$1</h2>');

        // Bold & Italic
        clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        clean = clean.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Line breaks
        clean = clean.replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>');

        return clean;
    }
}

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
    window.terminalApp = new TerminalApp();
});

// Global Tab Switcher Function (Resilient fallback for inline onclick)
window.switchPosTab = function(tabName) {
    if (window.terminalApp && typeof window.terminalApp.switchPosTab === "function") {
        window.terminalApp.switchPosTab(tabName);
        return;
    }
    const tabActive = document.getElementById("tab_active_positions");
    const tabHistory = document.getElementById("tab_trade_history");
    const viewActive = document.getElementById("view_active_positions");
    const viewHistory = document.getElementById("view_trade_history");

    if (tabName === "history") {
        if (tabHistory) tabHistory.classList.add("active");
        if (tabActive) tabActive.classList.remove("active");
        if (viewHistory) viewHistory.style.display = "flex";
        if (viewActive) viewActive.style.display = "none";
    } else {
        if (tabActive) tabActive.classList.add("active");
        if (tabHistory) tabHistory.classList.remove("active");
        if (viewActive) viewActive.style.display = "flex";
        if (viewHistory) viewHistory.style.display = "none";
    }
};
