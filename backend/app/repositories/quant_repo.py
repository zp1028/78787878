"""Persistence for PIT-safe feature snapshots and generated signals."""
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select, desc

from app.core.events import FeatureSnapshotEvent, SignalEvent
from app.db.models import FeatureSnapshotRow, SignalRow
from app.db.session import get_session


class QuantRepository:
    async def save_feature(self, event: FeatureSnapshotEvent) -> None:
        await asyncio.to_thread(self._save_feature, event)

    @staticmethod
    def _save_feature(event: FeatureSnapshotEvent) -> None:
        with get_session() as db:
            row = db.scalar(select(FeatureSnapshotRow).where(
                FeatureSnapshotRow.instrument_id == event.instrument_id,
                FeatureSnapshotRow.timeframe == event.timeframe,
                FeatureSnapshotRow.available_at == event.available_at,
            ))
            values = {
                "computed_at": event.computed_at,
                "available_at": event.available_at,
                "features": event.features,
                "source_snapshot_ids": [event.source_close_time],
            }
            if row is None:
                db.add(FeatureSnapshotRow(
                    instrument_id=event.instrument_id,
                    **values,
                ))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    async def save_signal(self, event: SignalEvent) -> None:
        await asyncio.to_thread(self._save_signal, event)

    @staticmethod
    def _save_signal(event: SignalEvent) -> None:
        with get_session() as db:
            db.add(SignalRow(
                instrument_id=event.instrument_id,
                symbol=event.symbol,
                signal_name=event.signal_name,
                direction=event.direction,
                strength=event.strength,
                timeframe=event.timeframe,
                features=event.features,
                source_timestamp=event.source_timestamp,
                generated_at=event.generated_at,
            ))

    def latest_feature_at(self, instrument_id: str, timeframe: str, analysis_time: int):
        with get_session() as db:
            return db.scalar(select(FeatureSnapshotRow).where(
                FeatureSnapshotRow.instrument_id == instrument_id,
                FeatureSnapshotRow.timeframe == timeframe,
                FeatureSnapshotRow.available_at <= analysis_time,
            ).order_by(desc(FeatureSnapshotRow.available_at)).limit(1))

    def signals_at(self, instrument_id: str, analysis_time: int, limit: int = 100):
        with get_session() as db:
            return list(db.scalars(select(SignalRow).where(
                SignalRow.instrument_id == instrument_id,
                SignalRow.source_timestamp <= analysis_time,
            ).order_by(desc(SignalRow.source_timestamp)).limit(limit)).all())
