from __future__ import annotations
from dataclasses import dataclass
from .contracts import MarketDataProvider, ProviderHealth

@dataclass(slots=True)
class RegisteredProvider:
    provider: MarketDataProvider
    priority: int

class MarketProviderRegistry:
    def __init__(self): self._providers: dict[str, RegisteredProvider] = {}
    def register(self, provider: MarketDataProvider, priority: int = 100):
        self._providers[provider.name] = RegisteredProvider(provider, priority)
    def list(self): return [x.provider for x in sorted(self._providers.values(), key=lambda x: x.priority)]
    def get(self, name: str): return self._providers[name].provider
    def choose(self, market: str):
        candidates=[x.provider for x in sorted(self._providers.values(), key=lambda x:x.priority) if x.provider.capabilities.market==market]
        if not candidates: raise LookupError(f'no provider for market={market}')
        return candidates[0]
    async def health(self) -> list[ProviderHealth]:
        out=[]
        for p in self.list():
            try:
                data=await p.health(); out.append(ProviderHealth(p.name, True, metadata=data or {}))
            except Exception as exc: out.append(ProviderHealth(p.name, False, last_error=str(exc)))
        return out
