from __future__ import annotations

import time
from typing import Any

import httpx


class BinanceUsdMTerminalService:
    """Read-only Binance USDⓈ-M terminal snapshot.

    This is deliberately a market-data adapter: no account, order or execution
    endpoint is exposed. Each snapshot carries source timestamps so the UI can
    distinguish fresh market facts from analytical output.
    """

    def __init__(self, base_url: str = "https://data-api.binance.vision", timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def snapshot(self, symbol: str, interval: str = "15m", depth_limit: int = 20, trade_limit: int = 20) -> dict[str, Any]:
        raw = symbol.replace("/", "").replace("-", "").upper()
        if not raw:
            raise ValueError("symbol is required")
        allowed = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"}
        if interval not in allowed:
            raise ValueError("unsupported interval")
        depth_limit = max(5, min(depth_limit, 100))
        trade_limit = max(5, min(trade_limit, 100))
        endpoints = {
            "ticker": f"/api/v3/ticker/24hr?symbol={raw}",
            "book": f"/api/v3/ticker/bookTicker?symbol={raw}",
            "depth": f"/api/v3/depth?symbol={raw}&limit={depth_limit}",
            "trades": f"/api/v3/trades?symbol={raw}&limit={trade_limit}",
            "premium": f"/api/v3/ticker/price?symbol={raw}",
            "klines": f"/api/v3/klines?symbol={raw}&interval={interval}&limit=180",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            responses = await self._gather(client, endpoints)

        ticker = self._json(responses["ticker"], {})
        if not isinstance(ticker, dict) or not ticker.get("symbol"):
            fallback = await self._okx_snapshot(raw, interval, depth_limit, trade_limit)
            if fallback is not None:
                return fallback

        ticker = ticker
        book = self._json(responses["book"], {})
        depth = self._json(responses["depth"], {})
        trades = self._json(responses["trades"], [])
        premium = self._json(responses["premium"], {})
        klines = self._json(responses["klines"], [])
        if not isinstance(ticker, dict) or not ticker.get("symbol"):
            raise RuntimeError("Binance USD-M ticker unavailable")

        now = int(time.time() * 1000)
        return {
            "analysis_only": True,
            "symbol": raw,
            "provider": "Binance Spot",
            "market_data_type": "SPOT",
            "server_time": now,
            "quote": {
                "last_price": self._float(ticker.get("lastPrice")),
                "price_change": self._float(ticker.get("priceChange")),
                "change_pct": self._float(ticker.get("priceChangePercent")),
                "high_24h": self._float(ticker.get("highPrice")),
                "low_24h": self._float(ticker.get("lowPrice")),
                "volume": self._float(ticker.get("volume")),
                "quote_volume": self._float(ticker.get("quoteVolume")),
                "trades": int(ticker.get("count", 0) or 0),
                "data_time": ticker.get("closeTime"),
            },
            "mark": {
                "mark_price": self._float(premium.get("markPrice")),
                "index_price": self._float(premium.get("indexPrice")),
                "funding_rate": self._float(premium.get("lastFundingRate")),
                "next_funding_time": premium.get("nextFundingTime"),
                "data_time": premium.get("time"),
            },
            "book": {
                "bid": self._float(book.get("bidPrice")),
                "bid_size": self._float(book.get("bidQty")),
                "ask": self._float(book.get("askPrice")),
                "ask_size": self._float(book.get("askQty")),
                "data_time": book.get("time"),
            },
            "depth": {
                "last_update_id": depth.get("lastUpdateId") if isinstance(depth, dict) else None,
                "bids": self._levels(depth.get("bids", []) if isinstance(depth, dict) else []),
                "asks": self._levels(depth.get("asks", []) if isinstance(depth, dict) else []),
            },
            "trades": self._trades(trades),
            "candles": self._candles(klines),
            "freshness": {
                "quote_ms": self._age(now, ticker.get("closeTime")),
                "mark_ms": self._age(now, premium.get("time")),
                "book_ms": self._age(now, book.get("time")),
                "status": "live" if self._age(now, ticker.get("closeTime")) is not None and self._age(now, ticker.get("closeTime")) < 15000 else "stale",
            },
        }

    async def _okx_snapshot(self, raw: str, interval: str, depth_limit: int, trade_limit: int) -> dict[str, Any] | None:
        bar_map = {"1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m","1h":"1H","2h":"2H","4h":"4H","6h":"6H","8h":"8H","12h":"12H","1d":"1D","3d":"3D","1w":"1W"}
        bar = bar_map.get(interval)
        if not bar: return None
        inst = raw[:-4] + "-USDT-SWAP" if raw.endswith("USDT") else raw + "-USDT-SWAP"
        base = "https://www.okx.com"
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent":"SmartTrader/1.0 analysis"}) as c:
            async def get(path, params):
                try:
                    r=await c.get(base+path,params=params); r.raise_for_status(); return r.json()
                except Exception: return {}
            ticker, mark, book, depth, trades, candles = await __import__('asyncio').gather(
                get('/api/v5/market/ticker', {'instId':inst}),
                get('/api/v5/public/mark-price', {'instType':'SWAP','instId':inst}),
                get('/api/v5/market/books', {'instId':inst,'sz':str(depth_limit)}),
                get('/api/v5/market/books', {'instId':inst,'sz':str(depth_limit)}),
                get('/api/v5/market/trades', {'instId':inst,'limit':str(trade_limit)}),
                get('/api/v5/market/candles', {'instId':inst,'bar':bar,'limit':'180'}),
            )
        t=((ticker.get('data') or [{}])[0] if isinstance(ticker,dict) else {})
        m=((mark.get('data') or [{}])[0] if isinstance(mark,dict) else {})
        b=((book.get('data') or [{}])[0] if isinstance(book,dict) else {})
        if not t.get('last'): return None
        def f(v):
            try: return float(v) if v not in (None,'') else None
            except (TypeError,ValueError): return None
        levels=b.get('bids',[]) if isinstance(b,dict) else []
        asks=b.get('asks',[]) if isinstance(b,dict) else []
        depth_rows={'bids':[{'price':f(x[0]),'qty':f(x[1])} for x in levels if isinstance(x,list) and len(x)>=2], 'asks':[{'price':f(x[0]),'qty':f(x[1])} for x in asks if isinstance(x,list) and len(x)>=2]}
        trade_rows=[]
        for x in (trades.get('data') or []) if isinstance(trades,dict) else []:
            trade_rows.append({'id':x.get('tradeId'),'price':f(x.get('px')),'qty':f(x.get('sz')),'buyer_maker':str(x.get('side','')).lower()=='sell','time':int(x.get('ts')) if str(x.get('ts','')).isdigit() else None})
        candle_rows=[]
        for x in reversed((candles.get('data') or []) if isinstance(candles,dict) else []):
            if isinstance(x,list) and len(x)>=6:
                candle_rows.append({'open_time':int(x[0]),'open':f(x[1]),'high':f(x[2]),'low':f(x[3]),'close':f(x[4]),'volume':f(x[5]),'close_time':int(x[0])})
        now=int(time.time()*1000)
        return {'analysis_only':True,'symbol':raw,'provider':'OKX SWAP public market data','market_data_type':'SWAP','server_time':now,
                'quote':{'last_price':f(t.get('last')),'price_change':(f(t.get('last')) or 0)-(f(t.get('open24h')) or f(t.get('last')) or 0),'change_pct':self._pct(t.get('last'),t.get('open24h')),'high_24h':f(t.get('high24h')),'low_24h':f(t.get('low24h')),'volume':f(t.get('vol24h')),'quote_volume':f(t.get('volCcy24h')),'trades':None,'data_time':int(t.get('ts')) if str(t.get('ts','')).isdigit() else None},
                'mark':{'mark_price':f(m.get('markPx')),'index_price':None,'funding_rate':None,'next_funding_time':None,'data_time':int(m.get('ts')) if str(m.get('ts','')).isdigit() else None},
                'book':{'bid':f(b.get('bids',[['']])[0][0]) if b.get('bids') else None,'bid_size':f(b.get('bids',[['','']])[0][1]) if b.get('bids') else None,'ask':f(b.get('asks',[['']])[0][0]) if b.get('asks') else None,'ask_size':f(b.get('asks',[['','']])[0][1]) if b.get('asks') else None,'data_time':int(b.get('ts')) if str(b.get('ts','')).isdigit() else None},
                'depth':{'last_update_id':None,**depth_rows},'trades':trade_rows,'candles':candle_rows,
                'freshness':{'quote_ms':self._age(now,t.get('ts')),'mark_ms':self._age(now,m.get('ts')),'book_ms':self._age(now,b.get('ts')),'status':'live' if self._age(now,t.get('ts')) is not None and self._age(now,t.get('ts'))<15000 else 'stale'}}

    @staticmethod
    def _pct(last: Any, prev: Any) -> float | None:
        try:
            a,b=float(last),float(prev)
            return (a-b)/b*100 if b else None
        except (TypeError,ValueError): return None

    async def _gather(self, client: httpx.AsyncClient, endpoints: dict[str, str]) -> dict[str, Any]:
        import asyncio
        tasks = {name: client.get(path) for name, path in endpoints.items()}
        values = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), values))

    @staticmethod
    def _json(response: Any, fallback: Any) -> Any:
        if isinstance(response, Exception):
            return fallback
        try:
            response.raise_for_status()
            return response.json()
        except Exception:
            return fallback

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _levels(cls, rows: Any) -> list[dict[str, float]]:
        out = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 2:
                continue
            price, qty = cls._float(row[0]), cls._float(row[1])
            if price is not None and qty is not None:
                out.append({"price": price, "qty": qty})
        return out

    @classmethod
    def _trades(cls, rows: Any) -> list[dict[str, Any]]:
        out = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            out.append({"id": row.get("id"), "price": cls._float(row.get("price")), "qty": cls._float(row.get("qty")), "buyer_maker": row.get("isBuyerMaker"), "time": row.get("time")})
        return out

    @classmethod
    def _candles(cls, rows: Any) -> list[dict[str, Any]]:
        out = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 7:
                continue
            out.append({"open_time": row[0], "open": cls._float(row[1]), "high": cls._float(row[2]), "low": cls._float(row[3]), "close": cls._float(row[4]), "volume": cls._float(row[5]), "close_time": row[6]})
        return out

    @staticmethod
    def _age(now: int, ts: Any) -> int | None:
        try:
            return max(0, now - int(ts)) if ts is not None else None
        except (TypeError, ValueError):
            return None
