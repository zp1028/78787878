from fastapi import APIRouter, Query
from app.services.crypto_derivatives import BinanceDerivativesService

router = APIRouter(tags=["derivatives"])
service = BinanceDerivativesService()

@router.get("/derivatives/crypto/{symbol}")
async def crypto_derivatives(symbol: str, period: str = Query("1h", pattern="^(5m|15m|30m|1h|2h|4h|6h|12h|1d)$")):
    return await service.snapshot(symbol, period)
