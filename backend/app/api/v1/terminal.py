from fastapi import APIRouter, Query

from app.core.config import settings
from app.services.binance_terminal import BinanceUsdMTerminalService

router = APIRouter(tags=["terminal"])
service = BinanceUsdMTerminalService(settings.binance_rest_url)


@router.get("/terminal/crypto/{symbol}")
async def crypto_terminal(
    symbol: str,
    interval: str = Query("15m"),
    depth_limit: int = Query(20, ge=5, le=100),
    trade_limit: int = Query(20, ge=5, le=100),
):
    return await service.snapshot(symbol, interval, depth_limit, trade_limit)
