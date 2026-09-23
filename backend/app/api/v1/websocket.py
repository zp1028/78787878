from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import (
    AIAnalysisCompletedEvent,
    AIAnalysisStartedEvent,
    ProviderSwitchEvent,
    AttentionEvent,
    CandleEvent,
    FeatureSnapshotEvent,
    MarketTickEvent,
    ObservationTriggeredEvent,
    SignalEvent,
    TradeEvent,
)
from app.main import bus, crypto_ws

router = APIRouter(tags=["websocket"])


class ClientHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def broadcast(self, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


hub = ClientHub()
_client_symbols: dict[WebSocket, set[str]] = {}
_client_lock = __import__("asyncio").Lock()


def _normalize_symbols(symbols) -> set[str]:
    return {str(s).upper().replace("/", "").replace("-", "") for s in symbols if str(s).strip()}


async def _reconcile_subscriptions() -> None:
    async with _client_lock:
        desired = set().union(*_client_symbols.values()) if _client_symbols else set()
        current = crypto_ws.subscriptions
        to_add = sorted(desired - current)
        to_remove = sorted(current - desired)
        if to_add:
            await crypto_ws.subscribe(to_add)
        if to_remove:
            await crypto_ws.unsubscribe(to_remove)


async def provider_switch_handler(event: ProviderSwitchEvent) -> None:
    await hub.broadcast({
        "event": "provider.changed",
        "timestamp": event.changed_at,
        "data": {
            "provider": event.provider,
            "previous_provider": event.previous_provider,
            "reason": event.reason,
        },
        "providers": crypto_ws.health_snapshot(),
    })


async def tick_handler(event: MarketTickEvent) -> None:
    await hub.broadcast(
        {
            "event": "market.tick",
            "timestamp": event.source_timestamp,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "symbol": event.symbol,
                "bid": event.bid,
                "ask": event.ask,
                "last": event.last,
                "bid_size": event.bid_size,
                "ask_size": event.ask_size,
                "received_at": event.received_at,
                "venue": event.venue,
            },
        }
    )


async def trade_handler(event: TradeEvent) -> None:
    await hub.broadcast(
        {
            "event": "market.trade",
            "timestamp": event.source_timestamp,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "symbol": event.symbol,
                "price": event.price,
                "quantity": event.quantity,
                "is_buyer_maker": event.is_buyer_maker,
                "received_at": event.received_at,
                "venue": event.venue,
            },
        }
    )


async def candle_handler(event: CandleEvent) -> None:
    await hub.broadcast(
        {
            "event": "market.candle",
            "timestamp": event.source_timestamp,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "symbol": event.symbol,
                "interval": event.interval,
                "open": event.open,
                "high": event.high,
                "low": event.low,
                "close": event.close,
                "volume": event.volume,
                "open_time": event.open_time,
                "close_time": event.close_time,
                "is_closed": event.is_closed,
                "received_at": event.received_at,
                "venue": event.venue,
            },
        }
    )


async def feature_handler(event: FeatureSnapshotEvent) -> None:
    await hub.broadcast(
        {
            "event": "feature.updated",
            "timestamp": event.available_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "timeframe": event.timeframe,
                "computed_at": event.computed_at,
                "available_at": event.available_at,
                "source_close_time": event.source_close_time,
                "features": event.features,
            },
        }
    )


async def signal_handler(event: SignalEvent) -> None:
    await hub.broadcast(
        {
            "event": "signal.generated",
            "timestamp": event.generated_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "signal_name": event.signal_name,
                "direction": event.direction,
                "strength": event.strength,
                "timeframe": event.timeframe,
                "features": event.features,
                "source_timestamp": event.source_timestamp,
            },
        }
    )


async def attention_handler(event: AttentionEvent) -> None:
    await hub.broadcast(
        {
            "event": "attention.updated",
            "timestamp": event.generated_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "score": event.score,
                "reasons": event.reasons,
                "regime": event.regime,
            },
        }
    )


async def observation_handler(event: ObservationTriggeredEvent) -> None:
    await hub.broadcast(
        {
            "event": "observation.triggered",
            "timestamp": event.triggered_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "observation_id": event.observation_id,
                "trigger_type": event.trigger_type,
                "trigger_value": event.trigger_value,
                "current_value": event.current_value,
            },
        }
    )




async def ai_started_handler(event: AIAnalysisStartedEvent) -> None:
    await hub.broadcast(
        {
            "event": "ai.analysis.started",
            "timestamp": event.started_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "analysis_id": event.analysis_id,
                "trigger": event.trigger,
            },
        }
    )


async def ai_completed_handler(event: AIAnalysisCompletedEvent) -> None:
    await hub.broadcast(
        {
            "event": "ai.analysis.completed",
            "timestamp": event.completed_at,
            "instrument_id": event.instrument_id,
            "instrument": event.symbol,
            "data": {
                "analysis_id": event.analysis_id,
                "duration_ms": event.duration_ms,
                "data_quality": event.data_quality,
                "result": event.result,
            },
        }
    )


bus.subscribe(ProviderSwitchEvent, provider_switch_handler)
bus.subscribe(MarketTickEvent, tick_handler)
bus.subscribe(TradeEvent, trade_handler)
bus.subscribe(CandleEvent, candle_handler)
bus.subscribe(FeatureSnapshotEvent, feature_handler)
bus.subscribe(SignalEvent, signal_handler)
bus.subscribe(AttentionEvent, attention_handler)
bus.subscribe(ObservationTriggeredEvent, observation_handler)
bus.subscribe(AIAnalysisStartedEvent, ai_started_handler)
bus.subscribe(AIAnalysisCompletedEvent, ai_completed_handler)


@router.websocket("/ws/market")
async def market_ws(websocket: WebSocket):
    await websocket.accept()
    hub.clients.add(websocket)
    _client_symbols[websocket] = set()
    try:
        await websocket.send_json(
            {
                "event": "connection.ready",
                "provider": crypto_ws.health.model_dump(),
                "providers": crypto_ws.health_snapshot(),
                "symbols": sorted(s.upper() for s in crypto_ws.subscriptions),
                "instruments": [i.model_dump() for i in crypto_ws.instruments.list_all()],
            }
        )
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            symbols = message.get("symbols", [])
            if action == "subscribe":
                normalized = _normalize_symbols(symbols)
                _client_symbols[websocket].update(normalized)
                await _reconcile_subscriptions()
                await websocket.send_json(
                    {"event": "subscription.updated", "action": "subscribe", "symbols": sorted(normalized)}
                )
            elif action == "unsubscribe":
                normalized = _normalize_symbols(symbols)
                _client_symbols[websocket].difference_update(normalized)
                await _reconcile_subscriptions()
                await websocket.send_json(
                    {"event": "subscription.updated", "action": "unsubscribe", "symbols": sorted(normalized)}
                )
            elif action == "health":
                await websocket.send_json(
                    {
                        "event": "provider.health",
                        "data": crypto_ws.health.model_dump(),
                        "providers": crypto_ws.health_snapshot(),
                    }
                )
            else:
                await websocket.send_json(
                    {"event": "error", "message": "unknown action"}
                )
    except WebSocketDisconnect:
        hub.clients.discard(websocket)
    finally:
        _client_symbols.pop(websocket, None)
        try:
            await _reconcile_subscriptions()
        except Exception:
            pass
