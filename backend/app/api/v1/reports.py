from fastapi import APIRouter, HTTPException, Query
from app.services.report_registry import catalog
from app.services.report_orchestrator import ReportOrchestrator

router = APIRouter(tags=["reports"])
orchestrator = ReportOrchestrator()

@router.get("/reports/catalog")
async def report_catalog():
    return catalog()

@router.get("/reports/scenes/{scene}")
async def report_scene(scene: str):
    try:
        return orchestrator.scene(scene)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown scene")

@router.get("/reports/instrument/{symbol}")
async def instrument_report_manifest(
    symbol: str,
    market: str = Query("crypto"),
    timeframe: str = Query("15m"),
):
    try:
        return await orchestrator.instrument_manifest(symbol, market, timeframe)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"instrument report manifest failed: {exc}") from exc

@router.get("/reports/instrument/{symbol}/detail")
async def instrument_report_detail(
    symbol: str,
    market: str = Query("crypto"),
    timeframe: str = Query("15m"),
):
    try:
        return await orchestrator.instrument_detail(symbol, market, timeframe)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"instrument detail failed: {exc}") from exc

@router.get("/reports/{report_key}/{symbol}")
async def report(
    report_key: str,
    symbol: str,
    market: str = Query("crypto"),
    timeframe: str = Query("15m"),
    limit: int = Query(250, ge=60, le=500),
):
    try:
        return await orchestrator.build(report_key, symbol, market, timeframe, limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown report type")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"report generation failed: {exc}") from exc
