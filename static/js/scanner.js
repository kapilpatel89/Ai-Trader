/**
 * Multi-Coin Market Scanner & Screener Component
 */

class MarketScannerUI {
    constructor(onSelectPair) {
        this.onSelectPair = onSelectPair;
        this.container = document.getElementById("coin_list");
        this.filterTabs = document.querySelectorAll(".filter-tab");
        this.searchInput = document.getElementById("coin_search");
        this.scanButton = document.getElementById("btn_run_scan");
        this.scanProgressLabel = document.getElementById("scan_progress_label");
        
        this.currentFilter = "all";
        this.searchQuery = "";
        this.coins = [];
        this.selectedSymbol = "B-BTC_USDT";

        this.initEvents();
    }

    initEvents() {
        this.filterTabs.forEach(tab => {
            tab.addEventListener("click", () => {
                this.filterTabs.forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                this.currentFilter = tab.getAttribute("data-filter");
                this.render();
            });
        });

        if (this.searchInput) {
            this.searchInput.addEventListener("input", (e) => {
                this.searchQuery = e.target.value.trim().toUpperCase();
                this.render();
            });
        }

        if (this.scanButton) {
            this.scanButton.addEventListener("click", () => this.triggerScan());
        }
    }

    async loadScannedResults() {
        try {
            // First always ensure all 505+ markets are loaded into memory
            await this.loadTopMarkets();

            const resp = await fetch("/api/scan/results");
            const data = await resp.json();
            
            if (data.results && data.results.length > 0) {
                this.mergeScanResults(data.results);
            }

            if (data.is_scanning) {
                this.pollScanProgress();
            }
        } catch (e) {
            console.error("[Scanner] Error loading results:", e);
        }
    }

    async loadTopMarkets() {
        try {
            const resp = await fetch("/api/markets");
            const data = await resp.json();
            if (data.markets && data.markets.length > 0) {
                this.coins = data.markets.map(m => ({
                    pair: m.symbol,
                    symbol: m.symbol,
                    clean_symbol: m.clean_symbol,
                    base_coin: m.base_coin,
                    current_price: m.price,
                    price_inr: m.price_inr || (m.price * (m.usdt_inr_rate || 100.74)),
                    usdt_inr_rate: m.usdt_inr_rate || 100.74,
                    change_24h: m.change_24h,
                    volume: m.volume,
                    score: 0,
                    action: "NEUTRAL",
                    rsi: 50,
                    orderbook: { imbalance_pct: 0 }
                }));
                this.render();
            }
        } catch (e) {
            console.error("[Scanner] Error loading markets:", e);
        }
    }

    mergeScanResults(results) {
        if (!results || results.length === 0) return;
        const resMap = new Map();
        results.forEach(r => {
            const s = r.pair || r.symbol;
            if (s) resMap.set(s, r);
        });

        this.coins.forEach(c => {
            const s = c.pair || c.symbol;
            if (resMap.has(s)) {
                const scanned = resMap.get(s);
                c.score = scanned.score;
                c.action = scanned.action;
                c.direction = scanned.direction;
                c.macro_trend = scanned.macro_trend;
                c.confidence = scanned.confidence;
                c.signals = scanned.signals;
                c.vol_surge = scanned.vol_surge;
                c.rsi = scanned.rsi;
                c.orderbook = scanned.orderbook;
                c.trade_setup = scanned.trade_setup;
                if (scanned.current_price && scanned.current_price > 0) {
                    c.current_price = scanned.current_price;
                }
            }
        });

        this.render();
    }

    async triggerScan() {
        if (this.scanButton) {
            this.scanButton.disabled = true;
            this.scanButton.innerHTML = `<i class="pulse-dot amber"></i> Scanning...`;
        }

        try {
            await fetch("/api/scan", { method: "POST" });
            this.pollScanProgress();
        } catch (e) {
            console.error("[Scanner] Trigger scan error:", e);
            if (this.scanButton) {
                this.scanButton.disabled = false;
                this.scanButton.innerHTML = `⚡ Scan All Futures`;
            }
        }
    }

    async pollScanProgress() {
        const interval = setInterval(async () => {
            try {
                const resp = await fetch("/api/scan/results");
                const data = await resp.json();
                
                if (this.scanProgressLabel && data.progress) {
                    this.scanProgressLabel.textContent = `Scanned ${data.progress.scanned}/${data.progress.total}: ${data.progress.current}`;
                }

                if (!data.is_scanning) {
                    clearInterval(interval);
                    if (this.scanButton) {
                        this.scanButton.disabled = false;
                        this.scanButton.innerHTML = `⚡ Scan All Futures`;
                    }
                    if (this.scanProgressLabel) {
                        this.scanProgressLabel.textContent = `Scan Complete (${data.total || data.results?.length || 0} analyzed)`;
                    }
                    if (data.results) {
                        this.mergeScanResults(data.results);
                    }
                }
            } catch (e) {
                clearInterval(interval);
            }
        }, 1500);
    }

    render() {
        if (!this.container) return;

        let filtered = this.coins;

        // Enhanced Fuzzy Search Filter across symbol, clean_symbol, and base_coin (handles JCT, JCT USDT, etc.)
        if (this.searchQuery) {
            const rawQ = this.searchQuery.trim().toUpperCase();
            const cleanQ = rawQ.replace(/[^A-Z0-9]/g, '');
            filtered = filtered.filter(c => {
                const sym = (c.pair || c.symbol || "").toUpperCase();
                const clean = (c.clean_symbol || sym).replace(/[^A-Z0-9]/g, '').toUpperCase();
                const base = (c.base_coin || "").toUpperCase();
                return sym.includes(rawQ) || 
                       clean.includes(cleanQ) || 
                       base.includes(cleanQ) ||
                       (clean.length >= 3 && cleanQ.includes(clean)) ||
                       (base.length >= 3 && cleanQ.includes(base));
            });
        }

        // Category Filter
        if (this.currentFilter === "movers") {
            filtered = [...filtered].sort((a, b) => Math.abs(b.change_24h || 0) - Math.abs(a.change_24h || 0)).filter(c => Math.abs(c.change_24h || 0) >= 0.8);
        } else if (this.currentFilter === "top") {
            filtered = filtered.filter(c => (c.action && c.action !== "WAIT (NEUTRAL)") || Math.abs(c.score || 0) >= 30);
        } else if (this.currentFilter === "longs" || this.currentFilter === "calls") {
            filtered = filtered.filter(c => c.action === "CALL (BUY)" || (c.score || 0) >= 25);
        } else if (this.currentFilter === "shorts" || this.currentFilter === "puts") {
            filtered = filtered.filter(c => c.action === "PUT (SELL)" || (c.score || 0) <= -25);
        } else if (this.currentFilter === "oversold") {
            filtered = filtered.filter(c => (c.rsi || 50) < 35);
        } else if (this.currentFilter === "whales") {
            filtered = filtered.filter(c => Math.abs(c.orderbook?.imbalance_pct || 0) >= 20);
        }

        if (filtered.length === 0) {
            this.container.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-dim); font-size: 12px;">No matching pairs found</div>`;
            return;
        }

        this.container.innerHTML = filtered.map(c => {
            const sym = c.pair || c.symbol || "";
            const clean = sym.replace("B-", "").replace("_", "/");
            const price = c.current_price || c.price || 0;
            const change = c.change_24h || 0;
            const score = c.score || 0;
            const isSelected = sym === this.selectedSymbol;
            
            let badge = "";
            if (c.action === "CALL (BUY)") {
                badge = `<span class="coin-badge badge-long" style="background:rgba(16,185,129,0.2);color:#10b981;border:1px solid rgba(16,185,129,0.4);font-weight:700;">🟢 CALL (BUY)</span>`;
            } else if (c.action === "PUT (SELL)") {
                badge = `<span class="coin-badge badge-short" style="background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.4);font-weight:700;">🔴 PUT (SELL)</span>`;
            } else if (score >= 35) {
                badge = `<span class="coin-badge badge-long">CALL +${score}</span>`;
            } else if (score <= -35) {
                badge = `<span class="coin-badge badge-short">PUT ${score}</span>`;
            } else if (c.rsi && c.rsi < 30) {
                badge = `<span class="coin-badge" style="background:rgba(56,189,248,0.18);color:#38bdf8;">RSI ${c.rsi}</span>`;
            }

            const changeClass = change >= 0 ? "stat-value up" : "stat-value down";
            const changePrefix = change >= 0 ? "+" : "";

            let priceDisplay = "--";
            if (price >= 1) {
                priceDisplay = `$${price.toFixed(2)}`;
            } else if (price > 0) {
                priceDisplay = price < 0.01 ? `$${price.toFixed(6)}` : `$${price.toFixed(4)}`;
            }

            const rate = c.usdt_inr_rate || window.currentUsdtInrRate || 100.74;
            const priceInr = c.price_inr || (price * rate);
            let inrDisplay = "";
            if (priceInr >= 10000000) {
                inrDisplay = `₹${(priceInr / 10000000).toFixed(2)}Cr`;
            } else if (priceInr >= 100000) {
                inrDisplay = `₹${(priceInr / 100000).toFixed(2)}L`;
            } else if (priceInr >= 1) {
                inrDisplay = `₹${priceInr.toLocaleString('en-IN', {maximumFractionDigits: 2})}`;
            } else if (priceInr > 0) {
                inrDisplay = `₹${priceInr.toFixed(4)}`;
            }

            // Detailed indicator breakdown (1h macro trend, RSI, Imbalance, R:R)
            let subDetails = [];
            if (c.macro_trend) {
                if (c.macro_trend.includes("BULLISH")) {
                    subDetails.push(`<span style="color:#10b981;font-weight:600;">1h ↗ Bull</span>`);
                } else if (c.macro_trend.includes("BEARISH")) {
                    subDetails.push(`<span style="color:#ef4444;font-weight:600;">1h ↘ Bear</span>`);
                } else {
                    subDetails.push(`<span style="color:var(--text-dim);">1h ↔ Range</span>`);
                }
            }
            if (c.rsi && c.rsi !== 50) {
                subDetails.push(`RSI: ${c.rsi}`);
            }
            if (c.orderbook && c.orderbook.imbalance_pct !== undefined) {
                const imb = c.orderbook.imbalance_pct;
                const imbColor = imb > 0 ? "#10b981" : imb < 0 ? "#ef4444" : "var(--text-dim)";
                subDetails.push(`<span style="color:${imbColor}">Depth: ${imb > 0 ? '+' : ''}${imb}%</span>`);
            }
            if (c.trade_setup && c.trade_setup.risk_reward) {
                subDetails.push(`R:R 1:${c.trade_setup.risk_reward}`);
            }
            const subText = subDetails.length > 0 ? subDetails.join(" • ") : 'Futures (INR Margin)';

            return `
                <div class="coin-row ${isSelected ? 'active' : ''}" data-symbol="${sym}">
                    <div class="coin-info">
                        <div class="coin-name">
                            ${clean} ${badge}
                            <button class="btn-coin-tg" data-tg-sym="${sym}" title="Send Sure Call Signal to Telegram" style="background:rgba(0,136,204,0.15);border:1px solid rgba(0,136,204,0.3);color:#38bdf8;cursor:pointer;font-size:10px;padding:2px 5px;margin-left:6px;border-radius:4px;font-weight:700;">✈️</button>
                        </div>
                        <div class="coin-sub">
                            ${subText}
                        </div>
                    </div>
                    <div class="coin-price-block">
                        <div class="coin-price">${priceDisplay} <span style="font-size:10px;color:var(--neon-cyan);font-weight:600;margin-left:3px;">${inrDisplay}</span></div>
                        <div class="coin-change ${changeClass}">${changePrefix}${change.toFixed(2)}%</div>
                    </div>
                </div>
            `;
        }).join("");

        // Attach fast click handlers
        this.container.querySelectorAll(".coin-row").forEach(row => {
            row.addEventListener("click", () => {
                const sym = row.getAttribute("data-symbol");
                this.selectedSymbol = sym;
                // Fast active class toggle without re-rendering all 500+ rows
                this.container.querySelectorAll(".coin-row.active").forEach(r => r.classList.remove("active"));
                row.classList.add("active");

                const coinObj = this.coins.find(c => (c.pair || c.symbol) === sym);
                if (this.onSelectPair) {
                    this.onSelectPair(sym, coinObj);
                }
            });
        });

        // Quick Telegram broadcast buttons on coin rows
        this.container.querySelectorAll(".btn-coin-tg").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const sym = btn.getAttribute("data-tg-sym");
                const orig = btn.textContent;
                btn.textContent = "⏳";
                try {
                    const resp = await fetch("/api/telegram/broadcast-signal", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ pair: sym, timeframe: "1h" })
                    });
                    const d = await resp.json();
                    if (resp.ok && d.success) {
                        btn.textContent = "✓";
                        if (window.terminalApp?.sound) window.terminalApp.sound.playAiAlert();
                        setTimeout(() => { btn.textContent = orig; }, 2000);
                    } else {
                        btn.textContent = orig;
                        alert(d.detail || d.message || "Could not broadcast signal.");
                    }
                } catch (err) {
                    btn.textContent = orig;
                    alert(`Error: ${err.message}`);
                }
            });
        });
    }
}

window.MarketScannerUI = MarketScannerUI;
