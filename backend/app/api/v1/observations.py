from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.main import observation_engine

router = APIRouter(tags=["observations"])


class CreateObservation(BaseModel):
    instrument_id: str
    symbol: str
    trigger_value: float
    direction: str = Field(default="cross", pattern="^(above|below|cross)$")
    trigger_type: str = "price"
    user_id: str | None = None


class ObservationOut(BaseModel):
    observation_id: str
    instrument_id: str
    symbol: str
    trigger_type: str
    trigger_value: float
    direction: str
    is_active: bool
    user_id: str | None = None
    last_triggered_at: int | None = None


@router.get("/observations", response_model=list[ObservationOut])
async def list_observations():
    return [
        ObservationOut(
            observation_id=n.observation_id,
            instrument_id=n.instrument_id,
            symbol=n.symbol,
            trigger_type=n.trigger_type,
            trigger_value=n.trigger_value,
            direction=n.direction,
            is_active=n.is_active,
            user_id=n.user_id,
            last_triggered_at=n.last_triggered_at,
        )
        for n in observation_engine.list_all()
    ]


@router.post("/observations", response_model=ObservationOut)
async def create_observation(body: CreateObservation):
    node = observation_engine.add(
        instrument_id=body.instrument_id,
        symbol=body.symbol,
        trigger_value=body.trigger_value,
        direction=body.direction,
        trigger_type=body.trigger_type,
        user_id=body.user_id,
    )
    return ObservationOut(
        observation_id=node.observation_id,
        instrument_id=node.instrument_id,
        symbol=node.symbol,
        trigger_type=node.trigger_type,
        trigger_value=node.trigger_value,
        direction=node.direction,
        is_active=node.is_active,
        user_id=node.user_id,
        last_triggered_at=node.last_triggered_at,
    )


@router.delete("/observations/{observation_id}")
async def delete_observation(observation_id: str):
    ok = observation_engine.remove(observation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="observation not found")
    return {"deleted": observation_id}
