"""Instrument persistence (PostgreSQL / SQLite)."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import InstrumentRow
from app.db.session import get_session
from app.models.instrument import (
    AssetType,
    ContractType,
    Instrument,
    InstrumentRegistry,
)


def _row_to_instrument(row: InstrumentRow) -> Instrument:
    return Instrument(
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        market=row.market,
        asset_type=AssetType(row.asset_type),
        venue=row.venue,
        quote_currency=row.quote_currency,
        base_currency=row.base_currency,
        contract_type=ContractType(row.contract_type),
        tick_size=row.tick_size,
        lot_size=row.lot_size,
        timezone=row.timezone,
        metadata=row.metadata_json or {},
    )


def upsert_instrument(instrument: Instrument) -> None:
    with get_session() as session:
        row = session.execute(
            select(InstrumentRow).where(InstrumentRow.instrument_id == instrument.instrument_id)
        ).scalar_one_or_none()
        if row is None:
            row = InstrumentRow(instrument_id=instrument.instrument_id)
            session.add(row)

        row.symbol = instrument.symbol
        row.market = instrument.market
        row.asset_type = instrument.asset_type.value
        row.venue = instrument.venue
        row.quote_currency = instrument.quote_currency
        row.base_currency = instrument.base_currency
        row.contract_type = instrument.contract_type.value
        row.tick_size = instrument.tick_size
        row.lot_size = instrument.lot_size
        row.timezone = instrument.timezone
        row.metadata_json = instrument.metadata


def load_all_into_registry(registry: InstrumentRegistry) -> int:
    with get_session() as session:
        rows = session.execute(select(InstrumentRow)).scalars().all()
        for row in rows:
            registry.register(_row_to_instrument(row))
        return len(rows)


def list_instruments() -> list[Instrument]:
    with get_session() as session:
        rows = session.execute(select(InstrumentRow)).scalars().all()
        return [_row_to_instrument(r) for r in rows]
