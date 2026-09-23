from fastapi import APIRouter, Query

from app.services.terminal_analysis import TerminalAnalysisService

router = APIRouter(tags=["terminal-analysis"])
service = TerminalAnalysisService()


@router.get("/terminal-analysis/crypto/{symbol}")
async def crypto_terminal_analysis(
    symbol: str,
    timeframe: str = Query("15m"),
    depth_limit: int = Query(20, ge=5, le=100),
    trade_limit: int = Query(20, ge=5, le=100),
):
    return await service.build(symbol, timeframe, depth_limit, trade_limit)
