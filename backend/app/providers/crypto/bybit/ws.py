from __future__ import annotations

import json
import time
from typing import Any

from app.core.events import CandleEvent, FundingRateEvent, MarketTickEvent, OpenInterestEvent, TradeEvent
from app.models.instrument import InstrumentRegistry
from app.providers.crypto.ws_base import CryptoWsProvider


INTERVALS = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720", "1d": "D", "1w": "W"}


class BybitWsClient(CryptoWsProvider):
    """Bybit V5 public linear stream, normalized to the internal event bus."""

    def __init__(self, settings: Any, bus, instruments: InstrumentRegistry):
        super().__init__("bybit", "wss://stream.bybit.com/v5/public/linear", settings, bus, instruments)
        self._last_prices: dict[str, float] = {}

    async def _send_subscription(self, action: str, symbols: set[str]) -> None:
        if not symbols:
            return
        args: list[str] = []
        interval = INTERVALS.get(getattr(self.settings, "binance_kline_interval", "1m"), "1")
        for symbol in symbols:
            args.extend([f"tickers.{symbol.upper()}", f"publicTrade.{symbol.upper()}", f"kline.{interval}.{symbol.upper()}"])
        await self._send_json({"op": action, "args": args})

    def _instrument_id(self, symbol: str) -> str:
        return self.instruments.ensure_crypto(symbol.upper(), venue="bybit").instrument_id

    async def _handle_raw(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        msg = json.loads(raw)
        if msg.get("op") in {"pong", "subscribe", "unsubscribe"} or msg.get("success") is True:
            return
        topic = str(msg.get("topic", ""))
        data = msg.get("data")
        received = int(time.time() * 1000)
        source_ts = int(msg.get("ts") or received)
        if topic.startswith("tickers.") and isinstance(data, dict):
            symbol = str(data.get("symbol") or topic.rsplit(".", 1)[-1]).upper()
            last = self._float(data.get("lastPrice"))
            if last is not None:
                self._last_prices[symbol] = last
            iid = self._instrument_id(symbol)
            await self.bus.publish(MarketTickEvent(
                instrument_id=iid, symbol=symbol,
                bid=self._float(data.get("bid1Price")), ask=self._float(data.get("ask1Price")),
                last=last, bid_size=self._float(data.get("bid1Size")), ask_size=self._float(data.get("ask1Size")),
                source_timestamp=source_ts, received_at=received, processed_at=received, venue="bybit"))
            funding = self._float(data.get("fundingRate"))
            if funding is not None:
                nxt = self._int(data.get("nextFundingTime"))
                await self.bus.publish(FundingRateEvent(iid, symbol, funding, nxt, source_ts, received, "bybit"))
            oi = self._float(data.get("openInterest"))
            if oi is not None:
                await self.bus.publish(OpenInterestEvent(iid, symbol, oi, self._float(data.get("openInterestValue")), source_ts, received, "bybit"))
            return
        if topic.startswith("publicTrade.") and isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("s") or topic.rsplit(".", 1)[-1]).upper()
                iid = self._instrument_id(symbol)
                await self.bus.publish(TradeEvent(
                    iid, symbol, self._float(item.get("p")) or 0.0, self._float(item.get("v")) or 0.0,
                    str(item.get("S", "")).lower() == "sell" if item.get("S") is not None else None,
                    self._int(item.get("T")) or source_ts, received, "bybit"))
            return
        if topic.startswith("kline.") and isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or topic.rsplit(".", 1)[-1]).upper()
                iid = self._instrument_id(symbol)
                interval = self._reverse_interval(str(item.get("interval") or topic.split(".")[1]))
                await self.bus.publish(CandleEvent(
                    iid, symbol, interval,
                    self._float(item.get("open")) or 0.0, self._float(item.get("high")) or 0.0,
                    self._float(item.get("low")) or 0.0, self._float(item.get("close")) or 0.0,
                    self._float(item.get("volume")) or 0.0, self._int(item.get("start")) or source_ts,
                    self._int(item.get("end")) or source_ts, bool(item.get("confirm")),
                    self._int(item.get("timestamp")) or source_ts, received, "bybit"))

    @staticmethod
    def _reverse_interval(v: str) -> str:
        return next((k for k, x in INTERVALS.items() if x == v), v)

    @staticmethod
    def _float(v: Any) -> float | None:
        try: return float(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _int(v: Any) -> int | None:
        try: return int(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None
