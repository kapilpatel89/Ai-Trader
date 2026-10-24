/**
 * Chart Manager for CoinDCX AI Trading Terminal
 * Implements TradingView Lightweight Charts with Volume & Entry / SL / TP Overlays
 */

class ChartManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.priceLines = [];
        this.currentPair = "B-BTC_USDT";
        this.currentInterval = "1h";
        this.candleCache = {};
        this.activeCandle = null;
        this.pendingTradeSetup = null;
        this.candleFetchId = 0;
        this.theme = document.documentElement.getAttribute("data-theme") || "light";
        
        this.initChart();
    }

    initChart() {
        if (!this.container || typeof LightweightCharts === "undefined") {
            console.warn("[Chart] LightweightCharts not loaded yet or container missing");
            return;
        }

        if (this.chart) {
            try { this.chart.remove(); } catch (e) {}
        }

        const isLight = this.theme === "light";

        this.chart = LightweightCharts.createChart(this.container, {
            layout: {
                background: { color: "transparent" },
                textColor: isLight ? "#475569" : "#8b9bb4",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11
            },
            grid: {
                vertLines: { color: isLight ? "rgba(166, 180, 200, 0.22)" : "rgba(255, 255, 255, 0.03)" },
                horzLines: { color: isLight ? "rgba(166, 180, 200, 0.22)" : "rgba(255, 255, 255, 0.03)" }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: isLight ? "rgba(2, 132, 199, 0.5)" : "rgba(0, 242, 254, 0.4)",
                    width: 1,
                    style: 2
                },
                horzLine: {
                    color: isLight ? "rgba(2, 132, 199, 0.5)" : "rgba(0, 242, 254, 0.4)",
                    width: 1,
                    style: 2
                }
            },
            rightPriceScale: {
                borderColor: isLight ? "rgba(166, 180, 200, 0.4)" : "rgba(255, 255, 255, 0.08)",
                autoScale: true
            },
            timeScale: {
                borderColor: isLight ? "rgba(166, 180, 200, 0.4)" : "rgba(255, 255, 255, 0.08)",
                timeVisible: true,
                secondsVisible: false
            }
        });

        // Candlestick Series
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#00ff87',
            downColor: '#ff3366',
            borderUpColor: '#00ff87',
            borderDownColor: '#ff3366',
            wickUpColor: '#00ff87',
            wickDownColor: '#ff3366'
        });

        // Volume Series (Bottom Histogram)
        this.volumeSeries = this.chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: '',
            scaleMargins: {
                top: 0.82,
                bottom: 0.0
            }
        });

        // Responsive auto-resize
        const ro = new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].target) return;
            const newRect = entries[0].contentRect;
            if (newRect.width > 0 && newRect.height > 0) {
                this.chart.applyOptions({ width: newRect.width, height: newRect.height });
            }
        });
        ro.observe(this.container);

        // Escape key to exit fullscreen
        window.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                const card = document.querySelector(".chart-card");
                if (card && card.classList.contains("fullscreen-active")) {
                    this.toggleFullscreen();
                }
            }
        });
    }

    toggleFullscreen() {
        const card = document.querySelector(".chart-card");
        if (!card) return false;
        const isFull = card.classList.toggle("fullscreen-active");

        let exitBtn = document.getElementById("fullscreen_exit_btn");
        if (isFull) {
            if (!exitBtn) {
                exitBtn = document.createElement("button");
                exitBtn.id = "fullscreen_exit_btn";
                exitBtn.className = "fullscreen-exit-btn";
                exitBtn.innerHTML = "✕ Exit Fullscreen (Esc)";
                exitBtn.addEventListener("click", () => this.toggleFullscreen());
                card.appendChild(exitBtn);
            }
            exitBtn.style.display = "block";
        } else if (exitBtn) {
            exitBtn.style.display = "none";
        }

        setTimeout(() => {
            if (this.chart && this.container) {
                const rect = this.container.getBoundingClientRect();
                this.chart.applyOptions({ width: rect.width, height: rect.height });
                this.chart.timeScale().scrollToRealTime();
            }
        }, 60);

        return isFull;
    }

    setTheme(theme) {
        this.theme = theme;
        if (!this.chart) return;
        const isLight = theme === "light";
        this.chart.applyOptions({
            layout: {
                textColor: isLight ? "#475569" : "#8b9bb4"
            },
            grid: {
                vertLines: { color: isLight ? "rgba(166, 180, 200, 0.22)" : "rgba(255, 255, 255, 0.03)" },
                horzLines: { color: isLight ? "rgba(166, 180, 200, 0.22)" : "rgba(255, 255, 255, 0.03)" }
            },
            crosshair: {
                vertLine: { color: isLight ? "rgba(2, 132, 199, 0.5)" : "rgba(0, 242, 254, 0.4)" },
                horzLine: { color: isLight ? "rgba(2, 132, 199, 0.5)" : "rgba(0, 242, 254, 0.4)" }
            },
            rightPriceScale: {
                borderColor: isLight ? "rgba(166, 180, 200, 0.4)" : "rgba(255, 255, 255, 0.08)"
            },
            timeScale: {
                borderColor: isLight ? "rgba(166, 180, 200, 0.4)" : "rgba(255, 255, 255, 0.08)"
            }
        });
    }

    getIntervalSeconds(interval) {
        switch(interval) {
            case "1m": return 60;
            case "5m": return 300;
            case "15m": return 900;
            case "30m": return 1800;
            case "1h": return 3600;
            case "2h": return 7200;
            case "4h": return 14400;
            case "1d": return 86400;
            default: return 3600;
        }
    }

    async loadCandles(pair, interval = "1h") {
        if (!this.chart || !this.candleSeries) {
            console.warn("[Chart] Cannot load candles: chart not initialized");
            return;
        }

        this.currentPair = pair;
        this.currentInterval = interval;
        const cacheKey = `${pair}_${interval}`;

        this.candleFetchId = (this.candleFetchId || 0) + 1;
        const fetchId = this.candleFetchId;

        this.clearPriceLines();
        this.pendingTradeSetup = null;

        // Instant render from cache if available
        if (this.candleCache[cacheKey]) {
            const cached = this.candleCache[cacheKey];
            this.candleSeries.setData(cached.candles);
            this.volumeSeries.setData(cached.volumes);
            if (cached.candles.length > 0) {
                this.activeCandle = { ...cached.candles[cached.candles.length - 1] };
                this.chart.priceScale('right').applyOptions({ autoScale: true });
                const total = cached.candles.length;
                this.chart.timeScale().setVisibleLogicalRange({
                    from: Math.max(0, total - 65),
                    to: total + 12
                });
            }
        }

        try {
            const resp = await fetch(`/api/candles/${pair}?interval=${interval}&limit=120`);
            if (!resp.ok) return;
            const data = await resp.json();

            if (!data.candles || data.candles.length === 0) {
                console.warn("[Chart] No candle data for", pair);
                return;
            }

            const rawList = [];
            data.candles.forEach(c => {
                const timeSec = typeof c.time === 'number' && c.time > 2000000000 ? Math.floor(c.time / 1000) : c.time;
                const o = parseFloat(c.open);
                const h = parseFloat(c.high);
                const l = parseFloat(c.low);
                const cl = parseFloat(c.close);
                const v = parseFloat(c.volume || 0);

                if (!isNaN(timeSec) && !isNaN(o) && !isNaN(h) && !isNaN(l) && !isNaN(cl)) {
                    rawList.push({
                        time: timeSec,
                        open: o,
                        high: Math.max(h, o, cl),
                        low: Math.min(l, o, cl),
                        close: cl,
                        volume: v
                    });
                }
            });

            rawList.sort((a, b) => a.time - b.time);
            const formattedCandles = [];
            const formattedVolumes = [];
            const seenTimes = new Set();

            rawList.forEach(c => {
                if (!seenTimes.has(c.time)) {
                    seenTimes.add(c.time);
                    formattedCandles.push({
                        time: c.time,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close
                    });
                    formattedVolumes.push({
                        time: c.time,
                        value: c.volume,
                        color: c.close >= c.open 
                            ? "rgba(0, 255, 135, 0.25)" 
                            : "rgba(255, 51, 102, 0.25)"
                    });
                }
            });

            if (formattedCandles.length === 0) return;
            if (this.candleFetchId !== fetchId || this.currentPair !== pair) return;

            this.candleCache[cacheKey] = {
                candles: formattedCandles,
                volumes: formattedVolumes
            };

            this.candleSeries.setData(formattedCandles);
            this.volumeSeries.setData(formattedVolumes);
            this.activeCandle = { ...formattedCandles[formattedCandles.length - 1] };
            
            this.chart.priceScale('right').applyOptions({ autoScale: true });

            if (this.pendingTradeSetup && (!this.pendingTradeSetup.pair || this.pendingTradeSetup.pair === pair)) {
                const setupToApply = this.pendingTradeSetup.setup;
                this.pendingTradeSetup = null;
                this.setTradePlanLines(setupToApply, pair);
            }

            const total = formattedCandles.length;
            this.chart.timeScale().setVisibleLogicalRange({
                from: Math.max(0, total - 65),
                to: total + 12
            });

        } catch (e) {
            console.error("[Chart] Error loading candles:", e);
        }
    }

    updateTick(price) {
        if (!this.activeCandle || !this.candleSeries || !price || price <= 0) return;

        try {
            const nowSec = Math.floor(Date.now() / 1000);
            const intervalSec = this.getIntervalSeconds(this.currentInterval);

            if (nowSec >= this.activeCandle.time + intervalSec) {
                const newTime = Math.max(this.activeCandle.time + intervalSec, nowSec - (nowSec % intervalSec));
                this.activeCandle = {
                    time: newTime,
                    open: price,
                    high: price,
                    low: price,
                    close: price
                };
            } else {
                this.activeCandle.high = Math.max(this.activeCandle.high, price);
                this.activeCandle.low = Math.min(this.activeCandle.low, price);
                this.activeCandle.close = price;
            }

            this.candleSeries.update(this.activeCandle);
        } catch (e) {
            console.warn("[Chart] updateTick skipped:", e);
        }
    }

    updateActiveCandle(candle) {
        if (!this.candleSeries || !candle) return;
        const timeSec = typeof candle.time === 'number' && candle.time > 2000000000 ? Math.floor(candle.time / 1000) : candle.time;
        const updated = {
            time: timeSec,
            open: parseFloat(candle.open),
            high: parseFloat(candle.high),
            low: parseFloat(candle.low),
            close: parseFloat(candle.close)
        };
        this.activeCandle = { ...updated };
        this.candleSeries.update(updated);
    }

    clearPriceLines() {
        if (!this.candleSeries) return;
        this.priceLines.forEach(line => {
            try { this.candleSeries.removePriceLine(line); } catch (e) {}
        });
        this.priceLines = [];
    }

    setTradePlanLines(setup, pair = null) {
        this.clearPriceLines();
        if (!setup || !this.candleSeries) return;
        if (pair && this.currentPair && pair !== this.currentPair) return;

        if (!this.activeCandle || !this.activeCandle.close) {
            this.pendingTradeSetup = { setup, pair: pair || this.currentPair };
            return;
        }

        const ref = this.activeCandle.close;
        const isValidPrice = (p) => typeof p === "number" && !isNaN(p) && p > 0 && p >= ref * 0.25 && p <= ref * 4.0;

        if (setup.entry && isValidPrice(setup.entry)) {
            this.priceLines.push(this.candleSeries.createPriceLine({
                price: setup.entry,
                color: '#00f2fe',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: `ENTRY (${setup.side || 'TRADE'})`
            }));
        }

        if (setup.stop_loss && isValidPrice(setup.stop_loss)) {
            this.priceLines.push(this.candleSeries.createPriceLine({
                price: setup.stop_loss,
                color: '#ff3366',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: 'STOP LOSS'
            }));
        }

        if (setup.take_profit_1 && isValidPrice(setup.take_profit_1)) {
            this.priceLines.push(this.candleSeries.createPriceLine({
                price: setup.take_profit_1,
                color: '#00ff87',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: 'TP 1'
            }));
        }

        if (setup.take_profit_2 && isValidPrice(setup.take_profit_2)) {
            this.priceLines.push(this.candleSeries.createPriceLine({
                price: setup.take_profit_2,
                color: '#00ff87',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'TP 2'
            }));
        }

        if (this.chart) {
            this.chart.priceScale('right').applyOptions({ autoScale: true });
        }
    }
}

window.ChartManager = ChartManager;