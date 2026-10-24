import asyncio
import aiohttp
import json

async def test():
    pairs = ['B-BTC_USDT', 'B-ETH_USDT', 'B-SOL_USDT', 'B-DOGE_USDT', 'B-1000PEPE_USDT', 'B-PEPE_USDT', 'B-XRP_USDT', 'B-ADA_USDT', 'B-HYPE_USDT', 'B-FARTCOIN_USDT']
    async with aiohttp.ClientSession() as s:
        for p in pairs:
            url1 = f"https://public.coindcx.com/market_data/candles/?pair={p}&interval=1h&limit=5"
            p_no_b = p.replace("B-", "")
            url2 = f"https://public.coindcx.com/market_data/candles/?pair={p_no_b}&interval=1h&limit=5"
            async with s.get(url1) as r1:
                d1 = await r1.json() if r1.status == 200 else []
            async with s.get(url2) as r2:
                d2 = await r2.json() if r2.status == 200 else []
            print(f"{p}: with_B={len(d1) if isinstance(d1, list) else 'err'}, no_B={len(d2) if isinstance(d2, list) else 'err'}")

if __name__ == '__main__':
    asyncio.run(test())
