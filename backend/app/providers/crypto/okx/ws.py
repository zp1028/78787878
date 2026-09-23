from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import websockets

from app.core.events import CandleEvent, MarketTickEvent, TradeEvent
from app.models.instrument import InstrumentRegistry
from app.providers.crypto.ws_base import CryptoWsProvider

PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
BUSINESS_URL = "wss://ws.okx.com:8443/ws/v5/business"
CANDLE_CHANNELS = {"1m": "candle1m", "3m": "candle3m", "5m": "candle5m", "15m": "candle15m", "30m": "candle30m", "1h": "candle1H", "2h": "candle2H", "4h": "candle4H", "6h": "candle6H", "12h": "candle12H", "1d": "candle1D", "1w": "candle1W"}


class OkxWsClient(CryptoWsProvider):
    """OKX public ticker/trade stream plus business candlestick stream."""

    def __init__(self, settings: Any, bus, instruments: InstrumentRegistry):
        super().__init__("okx", PUBLIC_URL, settings, bus, instruments)
        self._candle_ws = None
        self._candle_task: asyncio.Task | None = None
        self._candle_stop = asyncio.Event()
        self._last_prices: dict[str, float] = {}

    @staticmethod
    def _inst(symbol: str) -> str:
        s = symbol.upper().replace("/", "").replace("-", "")
        return s[:-4] + "-USDT-SWAP" if s.endswith("USDT") else s + "-USDT-SWAP"

    async def start(self) -> None:
        await super().start()
        if not self._candle_task or self._candle_task.done():
            self._candle_stop.clear()
            self._candle_task = asyncio.create_task(self._run_candles(), name="okx-candle-ws")

    async def stop(self) -> None:
        self._candle_stop.set()
        if self._candle_ws:
            await self._candle_ws.close()
        if self._candle_task:
            try:
                await self._candle_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def subscribe(self, symbols: list[str]) -> None:
        await super().subscribe(symbols)
        await self._candle_subscribe("subscribe", {self.normalize_symbol(s) for s in symbols if s})

    async def unsubscribe(self, symbols: list[str]) -> None:
        await super().unsubscribe(symbols)
        await self._candle_subscribe("unsubscribe", {self.normalize_symbol(s) for s in symbols if s})

    async def _send_subscription(self, action: str, symbols: set[str]) -> None:
        if not symbols:
            return
        args = []
        for symbol in symbols:
            args.extend([
                {"channel": "tickers", "instId": self._inst(symbol)},
                {"channel": "trades", "instId": self._inst(symbol)},
            ])
        await self._send_json({"op": action, "args": args})

    async def _heartbeat(self) -> None:
        await self._send_json({"op": "ping"})
        if self._candle_ws and not self._candle_ws.closed:
            await self._candle_ws.send("ping")

    async def _handle_raw(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        msg = json.loads(raw)
        if msg.get("event") in {"subscribe", "unsubscribe", "login", "pong"}:
            return
        arg = msg.get("arg") or {}
        channel = str(arg.get("channel", ""))
        data = msg.get("data") or []
        received = int(time.time() * 1000)
        if channel == "tickers":
            for item in data:
                symbol = self.normalize_symbol(str(item.get("instId", "")))
                if not symbol: continue
                last = self._float(item.get("last"))
                if last is not None: self._last_prices[symbol] = last
                iid = self.instruments.ensure_crypto(symbol, venue="okx").instrument_id
                ts = self._int(item.get("ts")) or received
                await self.bus.publish(MarketTickEvent(
                    iid, symbol, self._float(item.get("bidPx")), self._float(item.get("askPx")), last,
                    self._float(item.get("bidSz")), self._float(item.get("askSz")), ts, received, received, "okx"))
            return
        if channel == "trades":
            for item in data:
                symbol = self.normalize_symbol(str(item.get("instId", "")))
                if not symbol: continue
                iid = self.instruments.ensure_crypto(symbol, venue="okx").instrument_id
                ts = self._int(item.get("ts")) or received
                await self.bus.publish(TradeEvent(
                    iid, symbol, self._float(item.get("px")) or 0.0, self._float(item.get("sz")) or 0.0,
                    str(item.get("side", "")).lower() == "sell" if item.get("side") is not None else None,
                    ts, received, "okx"))

    async def _candle_subscribe(self, action: str, symbols: set[str]) -> None:
        if not self._candle_ws or self._candle_ws.closed or not symbols:
            return
        channel = CANDLE_CHANNELS.get(getattr(self.settings, "binance_kline_interval", "1m"), "candle1m")
        args = [{"channel": channel, "instId": self._inst(s)} for s in symbols]
        await self._candle_ws.send(json.dumps({"op": action, "args": args}, separators=(",", ":")))

    async def _run_candles(self) -> None:
        backoff = 1.0
        while not self._candle_stop.is_set():
            try:
                async with websockets.connect(BUSINESS_URL, ping_interval=20, ping_timeout=20, close_timeout=5, max_queue=4096) as ws:
                    self._candle_ws = ws
                    await self._candle_subscribe("subscribe", self.subscriptions)
                    backoff = 1.0
                    while not self._candle_stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        except asyncio.TimeoutError:
                            await ws.send("ping")
                            continue
                        if raw == "pong":
                            continue
                        await self._handle_candle(raw)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Public ticker/trade health remains authoritative; candle REST
                # recovery is still available when the business channel is down.
                await asyncio.sleep(min(backoff, 30.0))
                backoff = min(backoff * 2, 30.0)
            finally:
                self._candle_ws = None

    async def _handle_candle(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        msg = json.loads(raw)
        if msg.get("event") in {"subscribe", "unsubscribe", "pong"}: return
        arg = msg.get("arg") or {}
        channel = str(arg.get("channel", ""))
        if not channel.startswith("candle"): return
        interval = next((k for k, v in CANDLE_CHANNELS.items() if v == channel), channel.removeprefix("candle"))
        data = msg.get("data") or []
        received = int(time.time() * 1000)
        for x in data:
            if not isinstance(x, list) or len(x) < 6: continue
            symbol = self.normalize_symbol(str(arg.get("instId", "")))
            if not symbol: continue
            iid = self.instruments.ensure_crypto(symbol, venue="okx").instrument_id
            ts = self._int(x[0]) or received
            await self.bus.publish(CandleEvent(
                iid, symbol, interval, self._float(x[1]) or 0.0, self._float(x[2]) or 0.0,
                self._float(x[3]) or 0.0, self._float(x[4]) or 0.0, self._float(x[5]) or 0.0,
                ts, ts, str(x[8]) == "1" if len(x) > 8 else False, ts, received, "okx"))

    @staticmethod
    def _float(v: Any) -> float | None:
        try: return float(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _int(v: Any) -> int | None:
        try: return int(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None
