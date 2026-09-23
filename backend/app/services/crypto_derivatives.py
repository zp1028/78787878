from __future__ import annotations

from typing import Any
import httpx


class BinanceDerivativesService:
    """Read-only Binance USD-M derivatives analytics adapter.

    This service only reads public market-data endpoints. It never uses account
    credentials and never creates, cancels, or modifies orders.
    """
    # Spot public data endpoint as base; USD-M futures endpoints (fapi) are
    # usually blocked in restricted networks and fail fast with 404, letting
    # the OKX/Bybit fallback and the multi-exchange consensus fill what is
    # actually available.
    BASE = "https://data-api.binance.vision"

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    @staticmethod
    def normalize(symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").upper()

    async def snapshot(self, symbol: str, period: str = "1h") -> dict[str, Any]:
        s = self.normalize(symbol)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async def get(path: str, params: dict[str, Any]):
                r = await client.get(self.BASE + path, params=params)
                r.raise_for_status()
                return r.json()

            # These are public market-data calls. Failures are isolated so one
            # optional derivatives feed never hides the base instrument quote.
            results: dict[str, Any] = {}
            calls = {
                "premium": ("/fapi/v1/premiumIndex", {"symbol": s}),
                "open_interest": ("/fapi/v1/openInterest", {"symbol": s}),
                "funding_history": ("/fapi/v1/fundingRate", {"symbol": s, "limit": 30}),
                "long_short": ("/futures/data/globalLongShortAccountRatio", {"symbol": s, "period": period, "limit": 30}),
                "oi_history": ("/futures/data/openInterestHist", {"symbol": s, "period": period, "limit": 30}),
                "taker_flow": ("/futures/data/takerlongshortRatio", {"symbol": s, "period": period, "limit": 30}),
                "basis": ("/futures/data/basis", {"pair": s.replace("USDT", "USDT"), "contractType": "PERPETUAL", "period": period, "limit": 30}),
                "liquidations": ("/fapi/v1/allForceOrders", {"symbol": s, "limit": 50}),
            }
            for key, (path, params) in calls.items():
                try:
                    results[key] = await get(path, params)
                except Exception as exc:
                    results[key] = {"available": False, "reason": str(exc)}

        premium = results.get("premium", {})
        oi = results.get("open_interest", {})
        funding = results.get("funding_history", [])
        ls = results.get("long_short", [])
        oi_hist = results.get("oi_history", [])
        taker = results.get("taker_flow", [])
        basis = results.get("basis", [])
        liquidations = results.get("liquidations", [])

        if isinstance(premium, dict) and premium.get("markPrice"):
            premium = {
                "available": True,
                "mark_price": float(premium["markPrice"]),
                "index_price": float(premium["indexPrice"]),
                "last_funding_rate": float(premium.get("lastFundingRate", 0)),
                "next_funding_time": premium.get("nextFundingTime"),
                "time": premium.get("time"),
            }
        if isinstance(oi, dict) and oi.get("openInterest"):
            oi = {"available": True, "open_interest": float(oi["openInterest"]), "time": oi.get("time")}

        def clean_rows(rows: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
            if not isinstance(rows, list):
                return []
            out = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item: dict[str, Any] = {}
                for f in fields:
                    if f in row:
                        try:
                            item[f] = float(row[f]) if f not in {"timestamp"} else int(row[f])
                        except (TypeError, ValueError):
                            item[f] = row[f]
                if item:
                    out.append(item)
            return out

        funding_rows = clean_rows(funding, ("fundingTime", "fundingRate", "markPrice"))
        ls_rows = clean_rows(ls, ("timestamp", "longShortRatio", "longAccount", "shortAccount"))
        oi_rows = clean_rows(oi_hist, ("timestamp", "sumOpenInterest", "sumOpenInterestValue"))
        taker_rows = clean_rows(taker, ("timestamp", "buyVol", "sellVol", "buySellRatio"))
        basis_rows = clean_rows(basis, ("timestamp", "basis", "basisRate", "annualizedBasisRate", "futuresPrice", "indexPrice"))
        liquidation_rows = clean_rows(liquidations, ("time", "price", "origQty", "executedQty", "averagePrice"))

        latest_funding = funding_rows[-1] if funding_rows else None
        latest_ls = ls_rows[-1] if ls_rows else None
        latest_oi = oi_rows[-1] if oi_rows else None
        latest_taker = taker_rows[-1] if taker_rows else None
        latest_basis = basis_rows[-1] if basis_rows else None

        # Fill missing fields independently from the public OKX/Bybit adapters.
        try:
            from app.services.crypto_multi_exchange import CryptoMultiExchangeService
            mx = await CryptoMultiExchangeService(timeout=self.timeout).snapshot(symbol)
            available = [x for x in mx.get("providers", []) if x.get("available")]
            preferred = {"okx": None, "bybit": None, "binance": None}
            for item in available:
                preferred[str(item.get("provider", "")).lower()] = item
            ordered = [preferred.get("binance"), preferred.get("okx"), preferred.get("bybit")]
            ordered = [x for x in ordered if x]

            def first_value(key: str):
                for item in ordered:
                    value = item.get(key)
                    if value is not None:
                        return value, item.get("provider")
                return None, None

            mark_value = premium.get("mark_price") if isinstance(premium, dict) else None
            index_value = premium.get("index_price") if isinstance(premium, dict) else None
            funding_value = premium.get("last_funding_rate") if isinstance(premium, dict) else None
            oi_value = oi.get("open_interest") if isinstance(oi, dict) else None
            mark_source = "binance" if mark_value is not None else None
            index_source = "binance" if index_value is not None else None
            funding_source = "binance" if funding_value is not None else None
            oi_source = "binance" if oi_value is not None else None
            if mark_value is None:
                mark_value, mark_source = first_value("mark_price")
            if index_value is None:
                index_value, index_source = first_value("index_price")
            if funding_value is None:
                funding_value, funding_source = first_value("funding_rate")
            if oi_value is None:
                oi_value, oi_source = first_value("open_interest")
            if latest_funding is None and funding_value is not None:
                latest_funding = {"fundingRate": funding_value, "provider": funding_source}
            if latest_oi is None and oi_value is not None:
                latest_oi = {"open_interest": oi_value, "provider": oi_source}
            premium = {
                "available": mark_value is not None or index_value is not None,
                "mark_price": mark_value, "index_price": index_value,
                "last_funding_rate": funding_value,
                "next_funding_time": premium.get("next_funding_time") if isinstance(premium, dict) else None,
                "time": premium.get("time") if isinstance(premium, dict) else None,
                "provider": mark_source or index_source or funding_source,
            }
            oi = {"available": oi_value is not None, "open_interest": oi_value,
                  "time": oi.get("time") if isinstance(oi, dict) else None,
                  "provider": oi_source}
        except Exception:
            pass

        provider_names = []
        if isinstance(premium, dict) and premium.get("provider"):
            provider_names.append(str(premium["provider"]).upper())
        if isinstance(oi, dict) and oi.get("provider"):
            provider_names.append(str(oi["provider"]).upper())
        provider_label = "/".join(dict.fromkeys(provider_names)) or "public derivatives providers"

        return {
            "symbol": symbol,
            "provider": provider_label + " public market data",
            "available": any(isinstance(v, dict) and v.get("available") for v in (premium, oi)),
            "read_only": True,
            "funding": {"latest": latest_funding, "history": funding_rows},
            "open_interest": {"latest": oi if isinstance(oi, dict) else None, "history": oi_rows, "latest_history": latest_oi},
            "mark_index": premium if isinstance(premium, dict) else None,
            "long_short": {"latest": latest_ls, "history": ls_rows},
            "taker_flow": {"latest": latest_taker, "history": taker_rows},
            "basis": {"latest": latest_basis, "history": basis_rows},
            "liquidations": {"latest": liquidation_rows[-1] if liquidation_rows else None, "history": liquidation_rows},
            "capabilities": {
                "funding_rate": bool(funding_rows or (isinstance(premium, dict) and premium.get("last_funding_rate") is not None)),
                "open_interest": bool(oi_rows or (isinstance(oi, dict) and oi.get("open_interest") is not None)),
                "mark_index": bool(isinstance(premium, dict) and premium.get("mark_price") is not None),
                "long_short_ratio": bool(ls_rows),
                "taker_flow": bool(taker_rows),
                "basis": bool(basis_rows),
                "liquidations": bool(liquidation_rows),
            },
        }
