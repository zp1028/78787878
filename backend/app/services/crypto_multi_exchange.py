from __future__ import annotations
import asyncio
from typing import Any
import httpx


class CryptoMultiExchangeService:
    """Read-only public derivatives aggregation across Binance, OKX and Bybit."""
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    @staticmethod
    def normalize(symbol: str) -> str:
        return symbol.replace('/', '').replace('-', '').replace('_', '').upper()

    @staticmethod
    def _okx_inst(symbol: str) -> str:
        s = CryptoMultiExchangeService.normalize(symbol)
        if s.endswith('USDT'):
            return s[:-4] + '-USDT-SWAP'
        return s + '-USDT-SWAP'

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def _binance(self, c: httpx.AsyncClient, s: str) -> dict[str, Any]:
        base = 'https://data-api.binance.vision'
        async def one(path, params):
            try: return await self._get(c, base + path, params)
            except Exception as e: return {'available': False, 'reason': str(e)}
        price, avg, ex = await asyncio.gather(
            one('/api/v3/ticker/price', {'symbol': s}),
            one('/api/v3/avgPrice', {'symbol': s}),
            one('/api/v3/ticker/24hr', {'symbol': s}),
        )
        p = price if isinstance(price, dict) else {}
        return {'provider':'binance','available': bool(p.get('price')),
                'mark_price': float(p['price']) if p.get('price') else None,
                'index_price': float(ex['weightedAvgPrice']) if isinstance(ex,dict) and ex.get('weightedAvgPrice') else None,
                'funding_rate': None,
                'open_interest': None,
                'long_short': None}

    async def _okx(self, c: httpx.AsyncClient, s: str) -> dict[str, Any]:
        inst = self._okx_inst(s); base='https://www.okx.com'
        async def one(path, params):
            try: return await self._get(c, base + path, params)
            except Exception as e: return {'available':False,'reason':str(e)}
        tick, fund, oi = await asyncio.gather(
            one('/api/v5/market/ticker', {'instId':inst}),
            one('/api/v5/public/funding-rate', {'instId':inst}),
            one('/api/v5/public/open-interest', {'instType':'SWAP','instId':inst}),
        )
        t=(tick.get('data') or [{}])[0] if isinstance(tick,dict) else {}
        f=(fund.get('data') or [{}])[0] if isinstance(fund,dict) else {}
        o=(oi.get('data') or [{}])[0] if isinstance(oi,dict) else {}
        return {'provider':'okx','available':bool(t.get('last')),
                'mark_price':float(t['last']) if t.get('last') else None,
                'index_price':None,
                'funding_rate':float(f['fundingRate']) if f.get('fundingRate') else None,
                'open_interest':float(o['oi']) if o.get('oi') else None}

    async def _bybit(self, c: httpx.AsyncClient, s: str) -> dict[str, Any]:
        base='https://api.bybit.com'
        async def one(path, params):
            try: return await self._get(c, base + path, params)
            except Exception as e: return {'available':False,'reason':str(e)}
        tick, fund, oi = await asyncio.gather(
            one('/v5/market/tickers', {'category':'linear','symbol':s}),
            one('/v5/market/funding/history', {'category':'linear','symbol':s,'limit':1}),
            one('/v5/market/open-interest', {'category':'linear','symbol':s,'intervalTime':'1h','limit':1}),
        )
        t=(tick.get('result',{}).get('list') or [{}])[0] if isinstance(tick,dict) else {}
        f=(fund.get('result',{}).get('list') or [{}])[0] if isinstance(fund,dict) else {}
        o=(oi.get('result',{}).get('list') or [{}])[0] if isinstance(oi,dict) else {}
        return {'provider':'bybit','available':bool(t.get('lastPrice')),
                'mark_price':float(t['markPrice']) if t.get('markPrice') else None,
                'index_price':float(t['indexPrice']) if t.get('indexPrice') else None,
                'funding_rate':float(f['fundingRate']) if f.get('fundingRate') else None,
                'open_interest':float(o['openInterest']) if o.get('openInterest') else None}

    async def _gate(self, c: httpx.AsyncClient, s: str) -> dict[str, Any]:
        """Gate.io spot last price as a second live venue in the consensus."""
        pair = s[:-4] + '_' + s[-4:] if s.endswith(('USDT','USDC')) else s
        base='https://api.gateio.ws'
        try:
            tick=await self._get(c, base+'/api/v4/spot/tickers', {'currency_pair':pair})
        except Exception as e:
            return {'provider':'gate','available':False,'reason':str(e)}
        row=(tick or [{}])[0] if isinstance(tick,list) else {}
        return {'provider':'gate','available':bool(row.get('last')),
                'mark_price':float(row['last']) if row.get('last') else None,
                'index_price':None,
                'funding_rate':None,
                'open_interest':None}

    async def snapshot(self, symbol: str) -> dict[str, Any]:
        s=self.normalize(symbol)
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            rows=await asyncio.gather(self._binance(c,s), self._gate(c,s), self._okx(c,s), self._bybit(c,s))
        available=[r for r in rows if r.get('available')]
        def avg(key):
            vals=[r[key] for r in available if r.get(key) is not None]
            return sum(vals)/len(vals) if vals else None
        return {'symbol':symbol,'normalized_symbol':s,'read_only':True,
                'providers':rows,'available_provider_count':len(available),
                'consensus':{'mark_price_mean':avg('mark_price'),'funding_rate_mean':avg('funding_rate'),'open_interest_mean':avg('open_interest')},
                'divergence':{'funding_rate_spread': self._spread(available,'funding_rate'),
                              'mark_price_spread_pct': self._pct_spread(available,'mark_price')},
                'analysis_only':True}

    @staticmethod
    def _spread(rows,key):
        vals=[r[key] for r in rows if r.get(key) is not None]
        return max(vals)-min(vals) if len(vals)>=2 else None

    @staticmethod
    def _pct_spread(rows,key):
        vals=[r[key] for r in rows if r.get(key) is not None]
        if len(vals)<2 or min(vals)==0: return None
        return (max(vals)-min(vals))/min(vals)*100
