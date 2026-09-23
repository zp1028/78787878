from __future__ import annotations
from pydantic import BaseModel, Field

class AccountPosition(BaseModel):
    symbol: str
    quantity: float
    entry_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0

class AccountSnapshot(BaseModel):
    provider: str
    observed_at: int
    equity: float = Field(ge=0)
    available_balance: float = Field(ge=0)
    positions: list[AccountPosition] = []
    source_version: str = "1"

class ReconciliationResult(BaseModel):
    matched: bool
    missing_local: list[str] = []
    missing_remote: list[str] = []
    mismatched: list[str] = []
