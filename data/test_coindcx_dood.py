import asyncio
import aiohttp
import json

async def test_coindcx_endpoints():
    async with aiohttp.ClientSession() as s:
        urls = [
            "https://public.coindcx.com/market_data/candles/?pair=B-DOOD_USDT&interval=1h&limit=5",
            "https://public.coindcx.com/market_data/candles/?pair=DOOD_USDT&interval=1h&limit=5",
            "https://public.coindcx.com/market_data/candles/?pair=B-DOOD_USDT-futures&interval=1h&limit=5",
            "https://public.coindcx.com/market_data/v3/orderbook/B-DOOD_USDT-futures/10",
            "https://public.coindcx.com/market_data/v3/orderbook/B-DOOD_USDT/10",
            "https://public.coindcx.com/market_data/orderbook?pair=B-DOOD_USDT",
            "https://public.coindcx.com/market_data/trade_history?pair=B-DOOD_USDT",
            "https://api.coindcx.com/exchange/ticker",
            "https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments",
            "https://api.coindcx.com/exchange/v1/derivatives/futures/data/contract_details",
            "https://api.coindcx.com/exchange/v1/derivatives/futures/data/tickers",
            "https://api.coindcx.com/exchange/v1/derivatives/futures/positions"
        ]
        for url in urls:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                    print(f"URL: {url} -> Status: {r.status}")
                    if r.status == 200:
                        text = await r.text()
                        if "DOOD" in text:
                            print(f"  FOUND DOOD in {url}! Preview: {text[:300]}")
                        else:
                            print(f"  Status 200, length={len(text)} (DOOD not found in body)")
            except Exception as e:
                print(f"URL: {url} -> Error: {e}")

if __name__ == '__main__':
    asyncio.run(test_coindcx_endpoints())
