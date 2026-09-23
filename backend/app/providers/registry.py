from app.providers.base import MarketProvider

class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, MarketProvider] = {}

    def register(self, name: str, provider: MarketProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> MarketProvider:
        return self._providers[name]

    def health(self):
        return {name: provider.health for name, provider in self._providers.items()}
