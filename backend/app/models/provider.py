from enum import StrEnum
from pydantic import BaseModel

class ProviderStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    DOWN = "DOWN"
    CONNECTING = "CONNECTING"
    RECONNECTING = "RECONNECTING"

class ProviderHealth(BaseModel):
    name: str
    status: ProviderStatus
    latency_ms: float | None = None
    last_message: int | None = None
    reconnect_count: int = 0
    error_count: int = 0
    last_error: str | None = None
