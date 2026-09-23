from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.main import ai_orchestrator, instruments

router = APIRouter(tags=["analysis"])


class RunAnalysisRequest(BaseModel):
    instrument_id: str | None = None
    symbol: str | None = None
    timeframe: str = "1m"
    trigger: str = "manual"


@router.get("/analysis/{instrument_id}")
async def get_latest_analysis(instrument_id: str):
    result = ai_orchestrator.get_latest(instrument_id)
    if result is None:
        raise HTTPException(status_code=404, detail="no analysis yet")
    return result.model_dump()


@router.get("/analysis/{instrument_id}/history")
async def get_analysis_history(instrument_id: str, limit: int = 20):
    items = ai_orchestrator.get_history(instrument_id, limit=limit)
    return [r.model_dump() for r in items]


@router.post("/analysis/run")
async def run_analysis(body: RunAnalysisRequest):
    instrument_id = body.instrument_id
    symbol = body.symbol
    if not instrument_id and symbol:
        # try resolve from registry via binance venue default
        inst = instruments.get_by_symbol(
            symbol if "/" in symbol else f"{symbol.replace('USDT', '')}/USDT"
            if symbol.upper().endswith("USDT")
            else symbol,
            "binance",
        )
        if inst is None:
            # fallback: treat raw symbol as instrument key
            raw = symbol.upper().replace("/", "")
            instrument_id = f"binance:{raw}"
            symbol = symbol.upper()
        else:
            instrument_id = inst.instrument_id
            symbol = inst.symbol
    if not instrument_id or not symbol:
        raise HTTPException(status_code=400, detail="instrument_id or symbol required")

    result = await ai_orchestrator.run(
        instrument_id=instrument_id,
        symbol=symbol,
        trigger=body.trigger,
        timeframe=body.timeframe,
    )
    return result.model_dump()
