"""Unified analysis-only OHLCV provider for crypto, US/HK equities and commodities."""
from __future__ import annotations
import time
from typing import Any
import httpx
from app.data.klines import SUPPORTED_INTERVALS, fetch_binance_klines

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_INTERVALS = {"1m":"1m","3m":"5m","5m":"5m","15m":"15m","30m":"30m","1h":"1h","1d":"1d","1w":"1wk"}

def yahoo_symbol(symbol: str, market: str) -> str:
    raw=symbol.strip().upper()
    if market == "commodities": return raw if raw.endswith("=F") else raw+"=F"
    if market == "hk":
        if raw.endswith(".HK"): return raw
        return raw.zfill(4)+".HK"
    return raw

async def fetch_yahoo_klines(symbol: str, market: str, interval: str, limit: int=300) -> list[dict[str,Any]]:
    if interval not in SUPPORTED_INTERVALS: raise ValueError(f"unsupported interval {interval}")
    # Yahoo intraday limits are provider-specific. Request a safe range and let the API cap it.
    yint=YAHOO_INTERVALS.get(interval)
    if yint:
        ranges={"1m":"7d","5m":"60d","15m":"60d","30m":"60d","1h":"730d","1d":"10y","1w":"20y"}
        params={"interval":yint,"range":ranges.get(yint,"2y"),"includePrePost":"true","events":"div,splits"}
        async with httpx.AsyncClient(timeout=20,headers={"User-Agent":"SmartTrader/1.0 analysis"}) as client:
            r=await client.get(YAHOO_CHART.format(symbol=yahoo_symbol(symbol,market)),params=params); r.raise_for_status(); data=r.json()
        result=(data.get("chart") or {}).get("result") or []
        if not result: raise ValueError("provider returned no chart data")
        res=result[0]; q=(res.get("indicators") or {}).get("quote") or [{}]; q=q[0]
        ts=res.get("timestamp") or []; opens=q.get("open") or []; highs=q.get("high") or []; lows=q.get("low") or []; closes=q.get("close") or []; vols=q.get("volume") or []
        bars=[]
        for i,t in enumerate(ts):
            if i>=len(closes) or closes[i] is None: continue
            bars.append({"open_time":int(t*1000),"open":float(opens[i] if opens[i] is not None else closes[i]),"high":float(highs[i] if highs[i] is not None else closes[i]),"low":float(lows[i] if lows[i] is not None else closes[i]),"close":float(closes[i]),"volume":float(vols[i] or 0),"close_time":int(t*1000)})
        return bars[-max(10,min(limit,1500)):]
    # Aggregate from hourly Yahoo bars for 2h/4h/6h/12h.
    base=await fetch_yahoo_klines(symbol,market,"1h",min(1500,limit*12))
    hours={"2h":2,"4h":4,"6h":6,"12h":12}[interval]; out=[]
    bucket=[]
    for b in base:
        bucket.append(b)
        if len(bucket)==hours:
            out.append({"open_time":bucket[0]["open_time"],"open":bucket[0]["open"],"high":max(x["high"] for x in bucket),"low":min(x["low"] for x in bucket),"close":bucket[-1]["close"],"volume":sum(x["volume"] for x in bucket),"close_time":bucket[-1]["close_time"]}); bucket=[]
    return out[-limit:]

OKX_BARS = {"5m":"5m", "15m":"15m", "30m":"30m", "1h":"1H", "4h":"4H", "1d":"1D", "1w":"1W"}
BYBIT_INTERVALS = {"5m":"5", "15m":"15", "30m":"30", "1h":"60", "4h":"240", "1d":"D", "1w":"W"}

async def fetch_okx_klines(symbol: str, interval: str, limit: int=300) -> list[dict[str,Any]]:
    inst = symbol.upper().replace("/", "").replace("-", "")
    if inst.endswith("USDT"): inst = inst[:-4] + "-USDT-SWAP"
    bar = OKX_BARS.get(interval)
    if not bar: raise ValueError(f"unsupported OKX interval {interval}")
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent":"SmartTrader/1.0 analysis"}) as client:
        r = await client.get("https://www.okx.com/api/v5/market/candles", params={"instId":inst,"bar":bar,"limit":min(limit,300)})
        r.raise_for_status(); data=r.json()
    rows=(data.get("data") or []) if isinstance(data,dict) else []
    out=[]
    for x in reversed(rows):
        if not isinstance(x,list) or len(x)<6: continue
        try:
            out.append({"open_time":int(x[0]),"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"close_time":int(x[0]),"closed":str(x[8])=="1" if len(x)>8 else True})
        except (TypeError,ValueError): continue
    return out[-limit:]

async def fetch_bybit_klines(symbol: str, interval: str, limit: int=300) -> list[dict[str,Any]]:
    raw=symbol.upper().replace("/", "").replace("-", "")
    iv=BYBIT_INTERVALS.get(interval)
    if not iv: raise ValueError(f"unsupported Bybit interval {interval}")
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent":"SmartTrader/1.0 analysis"}) as client:
        r=await client.get("https://api.bybit.com/v5/market/kline",params={"category":"linear","symbol":raw,"interval":iv,"limit":min(limit,1000)})
        r.raise_for_status(); data=r.json()
    rows=((data.get("result") or {}).get("list") or []) if isinstance(data,dict) else []
    out=[]
    for x in reversed(rows):
        if not isinstance(x,list) or len(x)<6: continue
        try:
            out.append({"open_time":int(x[0]),"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"close_time":int(x[0]),"closed":True})
        except (TypeError,ValueError): continue
    return out[-limit:]

GATE_INTERVALS = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1h","4h":"4h","1d":"1d","1w":"1w"}

async def fetch_gate_klines(symbol: str, interval: str, limit: int=300) -> list[dict[str,Any]]:
    raw=symbol.upper().replace("/", "").replace("-", "")
    pair=raw[:-4]+"_"+raw[-4:] if raw.endswith(("USDT","USDC")) else raw
    iv=GATE_INTERVALS.get(interval)
    if not iv: raise ValueError(f"unsupported Gate interval {interval}")
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent":"SmartTrader/1.0 analysis"}) as client:
        r=await client.get("https://api.gateio.ws/api/v4/spot/candlesticks",params={"currency_pair":pair,"interval":iv,"limit":min(limit,300)})
        r.raise_for_status(); data=r.json()
    # Gate row format: [time_s, quote_volume, close, high, low, open, base_volume, closed]
    out=[]
    for x in reversed(data or []):
        if not isinstance(x,list) or len(x)<7: continue
        try:
            t=int(x[0])*1000
            out.append({"open_time":t,"open":float(x[5]),"high":float(x[3]),"low":float(x[4]),"close":float(x[2]),"volume":float(x[6]),"close_time":t,"closed":str(x[7]).lower()=="true" if len(x)>7 else True})
        except (TypeError,ValueError): continue
    return out[-limit:]

async def fetch_market_klines(symbol: str, market: str|None, interval: str="15m", limit: int=300):
    m=(market or "").lower()
    raw=symbol.upper().replace("/","").replace("-","")
    if not m:
        if raw.endswith("USDT") or raw.endswith("USDC"): m="crypto"
        elif raw.endswith("=F"): m="commodities"
        elif raw.endswith(".HK") or raw.isdigit(): m="hk"
        else: m="us"
    if m=="crypto":
        # The gateway owns provider order/failover. Keep this module as the
        # compatibility entry point for callers that only need bars.
        from app.services.crypto_provider_gateway import CryptoProviderGateway
        bars, _provider = await CryptoProviderGateway().fetch_klines(raw, interval, limit)
        return bars
    return await fetch_yahoo_klines(symbol,m,interval,limit)
