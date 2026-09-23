from fastapi import APIRouter, HTTPException

from app.quant.strategies import default_registry

router = APIRouter(tags=["strategies"])
registry = default_registry()


@router.get("/strategies")
async def list_strategies():
    return [
        {
            "id": s.id,
            "version": s.version,
            "key": s.key,
            "name": s.name,
            "description": s.description,
            "markets": list(s.markets),
            "timeframes": list(s.timeframes),
            "parameters": s.parameters,
        }
        for s in registry.list()
    ]


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    try:
        s = registry.get(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="strategy not found")
    return {
        "id": s.id,
        "version": s.version,
        "key": s.key,
        "name": s.name,
        "description": s.description,
        "markets": list(s.markets),
        "timeframes": list(s.timeframes),
        "parameters": s.parameters,
    }
