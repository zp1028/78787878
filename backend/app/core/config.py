from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Market data — Spot public data endpoint (data-api.binance.vision) as the
    # reachable default; original USD-M futures endpoint fapi.binance.com is
    # often blocked in restricted networks.
    binance_ws_url: str = "wss://fstream.binance.com/stream"
    binance_rest_url: str = "https://data-api.binance.vision"
    binance_market_data_ttl_seconds: float = 5.0
    binance_symbols: str = ""
    binance_kline_interval: str = "1m"
    ws_stale_seconds: float = 15.0
    ws_rotate_seconds: float = 84600.0
    ws_failover_grace_seconds: float = 8.0
    reconnect_base_seconds: float = 1.0
    reconnect_max_seconds: float = 30.0

    # Database — default to SQLite for zero-config local/dev; override with
    # postgresql+psycopg://user:pass@host:5432/smart_trader in production
    database_url: str = "sqlite:///./smart_trader.db"

    @property
    def symbols(self) -> list[str]:
        return [x.strip().upper() for x in self.binance_symbols.split(",") if x.strip()]


settings = Settings()
