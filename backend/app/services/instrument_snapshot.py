from __future__ import annotations
import time
from typing import Any
import httpx
from app.services.crypto_derivatives import BinanceDerivativesService
from app.services.crypto_provider_gateway import CryptoProviderGateway

TIMEFRAME_MAP = {
    '5m':'5m','15m':'15m','30m':'30m','1h':'1h','4h':'4h','1d':'1d','1w':'1wk'
}

class InstrumentSnapshotService:
    """Read-only quote/market-context adapters for the instrument detail page."""
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.derivatives = BinanceDerivativesService(timeout=timeout)
        self.crypto_gateway = CryptoProviderGateway(timeout=timeout)

    async def snapshot(self, symbol: str, market: str, timeframe: str = '1h') -> dict[str, Any]:
        market = market.lower(); symbol = symbol.strip(); timeframe = timeframe.lower()
        if market == 'crypto':
            return await self._crypto(symbol, timeframe)
        if market in {'us','commodities'}:
            return await self._yahoo(symbol, market, timeframe)
        if market == 'hk':
            return {'symbol': symbol, 'market': market, 'timeframe': timeframe,
                    'available': False, 'provider': 'configured HK provider',
                    'reason': 'HK quote provider must be configured/licensed; no fabricated quote is returned.'}
        return {'symbol': symbol, 'market': market, 'timeframe': timeframe, 'available': False, 'reason': 'unsupported market'}

    async def _yahoo(self, symbol: str, market: str, timeframe: str) -> dict[str, Any]:
        interval = TIMEFRAME_MAP.get(timeframe, '1h')
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'range': '1mo' if interval in {'5m','15m','30m','1h','4h'} else '1y', 'interval': interval}
        async with httpx.AsyncClient(timeout=self.timeout, headers={'User-Agent':'SmartTrader/1.3'}) as client:
            r = await client.get(url, params=params); r.raise_for_status(); raw = r.json()
        result = raw.get('chart', {}).get('result', [None])[0]
        if not result: raise RuntimeError('quote provider returned no chart data')
        meta = result.get('meta', {})
        ts = result.get('timestamp', [])
        q = (result.get('indicators', {}).get('quote') or [{}])[0]
        candles = []
        for i, t in enumerate(ts):
            row = {k: (q.get(k, [None]*len(ts))[i] if i < len(q.get(k, [])) else None) for k in ('open','high','low','close','volume')}
            if row['close'] is not None: candles.append({'timestamp': t, **row})
        return {'symbol': symbol, 'market': market, 'timeframe': timeframe, 'provider':'Yahoo-compatible chart',
                'available': bool(candles), 'realtime': False, 'data_time': candles[-1]['timestamp'] if candles else None,
                'quote': {'price': meta.get('regularMarketPrice'), 'previous_close': meta.get('previousClose'),
                          'currency': meta.get('currency'), 'exchange': meta.get('exchangeName')},
                'candles': candles[-200:], 'retrieved_at': time.time()}

    async def _crypto(self, symbol: str, timeframe: str) -> dict[str, Any]:
        interval = TIMEFRAME_MAP.get(timeframe, '1h')
        candles, candle_provider = await self.crypto_gateway.fetch_klines(symbol, interval, 200)
        derivatives = await self.derivatives.snapshot(symbol, period=timeframe if timeframe in {'5m','15m','30m','1h','4h','1d'} else '1h')
        mark = derivatives.get('mark_index') or {}
        price = mark.get('mark_price')
        available = bool(candles)
        provider = f'{candle_provider.upper()} public market data'
        return {
            'symbol':symbol,'market':'crypto','timeframe':timeframe,'provider':provider,'available':available,
            'realtime':available,'data_time':candles[-1].get('open_time') if candles else None,
            'quote':{'price':price,'previous_close':None,'change_pct':None,'volume':candles[-1].get('volume') if candles else None,
                     'bid':None,'ask':None,'mark_price':mark.get('mark_price'),'index_price':mark.get('index_price'),
                     'funding_rate':mark.get('last_funding_rate')},
            'candles':candles, 'derivatives':derivatives, 'retrieved_at':time.time()
        }
