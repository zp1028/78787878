from fastapi import APIRouter, HTTPException, Query
from app.services.instrument_snapshot import InstrumentSnapshotService

router = APIRouter(tags=['instrument-detail'])
service = InstrumentSnapshotService()

@router.get('/instrument/{market}/{symbol}/snapshot')
async def instrument_snapshot(market: str, symbol: str, timeframe: str = Query('1h')):
    try:
        return {'analysis_only': True, **await service.snapshot(symbol, market, timeframe)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'instrument data unavailable: {exc}') from exc
