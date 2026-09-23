from fastapi import APIRouter, HTTPException, Query
from app.main import attention_engine, instruments
from app.services.analysis_feedback import AnalysisFeedbackService

router = APIRouter(tags=["analysis-feed"])
service = AnalysisFeedbackService()

@router.get("/analysis-feed")
async def analysis_feed(market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(8, ge=1, le=20)):
    try:
        ranked = [e.symbol for e in attention_engine.ranking(max(20, limit * 3))]
        universe_symbols = [x.symbol for x in instruments.list_all() if getattr(x, "market", "") == market]
        if universe_symbols:
            ranked = [s for s in ranked if s in universe_symbols] + [s for s in universe_symbols if s not in ranked]
        elif not ranked:
            ranked = [x.symbol for x in instruments.list_all()] if hasattr(instruments, "list_all") else []
        return await service.feed(market, timeframe, ranked, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analysis feed failed: {exc}") from exc

@router.get("/analysis-feedback/{symbol:path}")
async def analysis_feedback(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m")):
    try:
        snapshot = await service.capture(symbol, market, timeframe, 250)
        return service.feedback_for(symbol, market, timeframe, snapshot.get("price_at_report"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analysis feedback failed: {exc}") from exc

@router.get("/analysis-feedback/{symbol:path}/with-price")
async def analysis_feedback_with_price(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), price: float | None = Query(None)):
    try:
        return service.feedback_for(symbol, market, timeframe, price)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analysis feedback failed: {exc}") from exc
