/**
 * Order Book & Microstructure Depth Visualizer - CoinDCX AI Terminal
 */

class OrderbookVisualizer {
    constructor() {
        this.bidsContainer = document.getElementById("ob_bids");
        this.asksContainer = document.getElementById("ob_asks");
        this.gaugeFill = document.getElementById("imbalance_gauge_fill");
        this.imbalanceLabel = document.getElementById("imbalance_label");
        this.spreadLabel = document.getElementById("spread_label");
        this.deltaLabel = document.getElementById("ob_delta_label");
        this.whaleWallsContainer = document.getElementById("whale_walls_container");
    }

    render(obData, currentPrice) {
        if (!obData) return;

        // Update Imbalance Gauge
        const imbPct = obData.imbalance_pct || 0;
        if (this.gaugeFill) {
            const fillWidth = Math.max(5, Math.min(95, ((imbPct + 100) / 2)));
            this.gaugeFill.style.width = `${fillWidth}%`;
            this.gaugeFill.style.background = imbPct >= 0 ? "var(--bullish)" : "var(--bearish)";
        }

        if (this.imbalanceLabel) {
            const prefix = imbPct > 0 ? "+" : "";
            this.imbalanceLabel.textContent = `${prefix}${imbPct}% (${obData.sentiment || 'Neutral'})`;
            this.imbalanceLabel.style.color = imbPct >= 0 ? "var(--bullish)" : "var(--bearish)";
        }

        if (this.spreadLabel) {
            this.spreadLabel.textContent = `Spread: ${obData.spread_bps || 0} bps`;
        }

        // Render Orderbook Delta & Microstructure Flow
        if (this.deltaLabel && obData.orderbook_delta !== undefined) {
            const delta = obData.orderbook_delta;
            const prefix = delta >= 0 ? "+" : "";
            const microStr = obData.microstructure_delta_pct !== undefined ? ` (Flow: ${obData.microstructure_delta_pct >= 0 ? '+' : ''}${obData.microstructure_delta_pct}%)` : '';
            this.deltaLabel.textContent = `Delta: ${prefix}${Number(delta).toLocaleString('en-US', {maximumFractionDigits: 1})}${microStr}`;
            this.deltaLabel.style.color = delta >= 0 ? "var(--bullish)" : "var(--bearish)";
        }

        // Render Bids (highest buy price first)
        if (this.bidsContainer && obData.bids_depth) {
            const maxBidQty = Math.max(...obData.bids_depth.map(b => b.qty), 1);
            this.bidsContainer.innerHTML = obData.bids_depth.slice(0, 10).map(b => {
                const depthPct = Math.min(100, (b.qty / maxBidQty) * 100);
                const p = Number(b.price);
                const pStr = p >= 1 ? p.toFixed(2) : (p < 0.01 ? p.toFixed(6) : p.toFixed(4));
                return `
                    <div class="ob-row">
                        <div class="ob-depth-bar bid" style="width: ${depthPct}%;"></div>
                        <span class="bid-price">${pStr}</span>
                        <span>${Number(b.qty).toFixed(2)}</span>
                    </div>
                `;
            }).join("");
        }

        // Render Asks (lowest sell price first)
        if (this.asksContainer && obData.asks_depth) {
            const maxAskQty = Math.max(...obData.asks_depth.map(a => a.qty), 1);
            this.asksContainer.innerHTML = obData.asks_depth.slice(0, 10).map(a => {
                const depthPct = Math.min(100, (a.qty / maxAskQty) * 100);
                const p = Number(a.price);
                const pStr = p >= 1 ? p.toFixed(2) : (p < 0.01 ? p.toFixed(6) : p.toFixed(4));
                return `
                    <div class="ob-row">
                        <div class="ob-depth-bar ask" style="width: ${depthPct}%;"></div>
                        <span class="ask-price">${pStr}</span>
                        <span>${Number(a.qty).toFixed(2)}</span>
                    </div>
                `;
            }).join("");
        }

        // Render Whale Liquidity Walls
        if (this.whaleWallsContainer && obData.whale_walls) {
            const walls = obData.whale_walls;
            if (walls.length === 0) {
                this.whaleWallsContainer.innerHTML = `<span style="font-size:11px;color:var(--text-dim)">No abnormal wall clusters detected</span>`;
            } else {
                this.whaleWallsContainer.innerHTML = walls.slice(0, 4).map(w => {
                    const isBid = w.side === 'BID';
                    return `
                        <div class="whale-wall-item ${isBid ? 'wall-bid' : 'wall-ask'}">
                            <span>${isBid ? '🟢 BUY WALL' : '🔴 SELL WALL'} @ $${Number(w.price).toFixed(2)}</span>
                            <span><strong>${Number(w.notional).toLocaleString('en-US', {style:'currency', currency:'USD', maximumFractionDigits:0})}</strong></span>
                        </div>
                    `;
                }).join("");
            }
        }
    }

    updateQuickStats(imbPct, spreadBps) {
        if (imbPct === undefined) return;
        if (this.gaugeFill) {
            const fillWidth = Math.max(5, Math.min(95, ((imbPct + 100) / 2)));
            this.gaugeFill.style.width = `${fillWidth}%`;
            this.gaugeFill.style.background = imbPct >= 0 ? "var(--bullish)" : "var(--bearish)";
        }
        if (this.imbalanceLabel) {
            const prefix = imbPct > 0 ? "+" : "";
            const sentiment = imbPct > 20 ? "Strong Bullish" : imbPct > 8 ? "Bullish" : imbPct < -20 ? "Strong Bearish" : imbPct < -8 ? "Bearish" : "Neutral";
            this.imbalanceLabel.textContent = `${prefix}${Number(imbPct).toFixed(1)}% (${sentiment})`;
            this.imbalanceLabel.style.color = imbPct >= 0 ? "var(--bullish)" : "var(--bearish)";
        }
        if (this.spreadLabel && spreadBps !== undefined) {
            this.spreadLabel.textContent = `Spread: ${Number(spreadBps).toFixed(1)} bps`;
        }
    }
}

window.OrderbookVisualizer = OrderbookVisualizer;
