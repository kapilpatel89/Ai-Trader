import asyncio
from backend.coindcx_client import CoinDCXClient

async def check_dood():
    c = CoinDCXClient()
    instruments = await c.get_active_futures_instruments()
    dood_inst = [i for i in instruments if 'DOOD' in i.upper()]
    print('Instruments matching DOOD:', dood_inst)
    
    tickers = await c.get_all_tickers()
    dood_tickers = [t for t in tickers if 'DOOD' in str(t.get('market', '')).upper()]
    print('Tickers matching DOOD:', dood_tickers)
    
    current_prices = await c.get_current_prices()
    dood_prices = {k: v for k, v in current_prices.items() if 'DOOD' in k.upper()}
    print('Current prices matching DOOD:', dood_prices)

    test_pairs = dood_inst + ['B-DOOD_USDT', 'DOOD_USDT', 'B-1000DOOD_USDT']
    for pair in set(test_pairs):
        cand = await c.get_candles(pair, '1h', 5)
        live = await c.get_live_price(pair)
        ob = await c.get_orderbook(pair, 5)
        has_bids = bool(ob.get('bids'))
        print(f'{pair}: live={live}, candles_len={len(cand)}, ob_bids={has_bids}')
    await c.close()

if __name__ == '__main__':
    asyncio.run(check_dood())
