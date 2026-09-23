from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db.models import CandleRow
from app.db.session import get_session
from app.models.instrument import InstrumentRegistry
from app.services.instrument_snapshot import InstrumentSnapshotService

router = APIRouter(prefix="/candles", tags=["candles"])
instruments = InstrumentRegistry()
snapshot_service = InstrumentSnapshotService()


@router.get("/{symbol}")
async def candles(
    symbol: str,
    timeframe: str = Query("15m"),
    market: str = Query("crypto"),
    limit: int = Query(200, ge=10, le=1500),
):
    """Read-only chart feed for every supported market.

    Crypto candles use the unified CryptoProviderGateway with the configured
    Binance → OKX → Bybit order; US/commodities use the configured Yahoo-compatible
    chart provider. HK stays explicitly unavailable until a licensed/configured
    provider is supplied.
    """
    try:
        data = await snapshot_service.snapshot(symbol, market, timeframe)
    except Exception as exc:
        raise HTTPException(502, f"candle provider error: {exc}") from exc
    rows = data.get("candles", [])[-limit:]
    normalized = []
    for r in rows:
        ts = int(r.get("timestamp", r.get("open_time", 0)) or 0)
        normalized.append({
            "open_time": ts, "close_time": ts,
            "open": r.get("open"), "high": r.get("high"),
            "low": r.get("low"), "close": r.get("close"),
            "volume": r.get("volume", 0), "closed": r.get("closed", True),
        })
    return {
        "symbol": data.get("symbol", symbol), "market": market,
        "timeframe": timeframe, "count": len(normalized),
        "stale": not bool(normalized), "provider": data.get("provider", "unknown"),
        "realtime": bool(data.get("realtime", False)),
        "data_time": data.get("data_time"), "candles": normalized,
    }
