from fastapi import APIRouter, HTTPException
from app.services.crypto_multi_exchange import CryptoMultiExchangeService

router = APIRouter(tags=['crypto-aggregation'])
service = CryptoMultiExchangeService()

@router.get('/crypto/{symbol}/multi-exchange')
async def crypto_multi_exchange(symbol: str):
    try:
        return await service.snapshot(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'crypto aggregation unavailable: {exc}') from exc
