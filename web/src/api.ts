// API client — talks to the Smart Trader FastAPI backend.
// In dev, /api is proxied to :8000 by Vite; in prod the frontend is served by
// the backend itself on the same origin.

const BASE = "/api/v1";
const TIMEOUT_MS = 25000;

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url.toString(), { headers: { Accept: "application/json" }, signal: controller.signal });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  runtimeStatus: () => get<import("./types").RuntimeStatus>("/runtime/status"),
  markets: (params: { market?: string; q?: string; limit?: number; offset?: number }) =>
    get<import("./types").MarketsResponse>("/markets", { ...params, market: params.market ?? "crypto" }),
  market: (symbol: string) => get<import("./types").MarketRow>(`/markets/${encodeURIComponent(symbol)}`),
  providerHealth: () => get<import("./types").ProviderHealthResponse>("/markets/providers/health"),
  marketCoverage: () => get<import("./types").MarketCoverageResponse>("/markets/coverage"),
  marketCapabilities: () => get<import("./types").MarketCapabilitiesResponse>("/market-capabilities"),
  candles: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").CandlesResponse>(`/candles/${encodeURIComponent(symbol)}`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 300 }),
  indicators: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").IndicatorReport>(`/indicators/${encodeURIComponent(symbol)}`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 300 }),
  structure: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").StructureResponse>(`/analysis/${encodeURIComponent(symbol)}/structure`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 200 }),
  scenarios: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").ScenarioAnalysis>(`/analysis/${encodeURIComponent(symbol)}/scenarios`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 200 }),
  riskMap: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").RiskMapResponse>(`/analysis/${encodeURIComponent(symbol)}/risk-map`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 160 }),
  unifiedReport: (symbol: string, params: { timeframe?: string; market?: string; limit?: number }) =>
    get<import("./types").UnifiedReport>(`/unified-report/${encodeURIComponent(symbol)}`, { timeframe: params.timeframe ?? "15m", market: params.market ?? "crypto", limit: params.limit ?? 250 }),
  analysisFeed: (params: { market?: string; timeframe?: string; limit?: number }) =>
    get<import("./types").AnalysisFeedResponse>("/analysis-feed", { market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m", limit: params.limit ?? 8 }),
  analysisFeedback: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").AnalysisFeedbackResponse>(`/analysis-feedback/${encodeURIComponent(symbol)}`, { market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m" }),
  reportsCatalog: () => get<import("./types").ReportCatalogResponse>("/reports/catalog"),
  derivatives: (symbol: string, params: { period?: string }) =>
    get<import("./types").DerivativesResponse>(`/derivatives/crypto/${encodeURIComponent(symbol)}`, { period: params.period ?? "1h" }),
  multiExchange: (symbol: string) =>
    get<import("./types").MultiExchangeResponse>(`/crypto/${encodeURIComponent(symbol)}/multi-exchange`),
  terminal: (symbol: string, params: { interval?: string }) =>
    get<import("./types").TerminalResponse>(`/terminal/crypto/${encodeURIComponent(symbol)}`, { interval: params.interval ?? "15m" }),
  instrumentAnalysisSnapshot: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").InstrumentAnalysisSnapshot>(`/instrument/${params.market ?? "crypto"}/${encodeURIComponent(symbol)}/analysis`, { timeframe: params.timeframe ?? "15m" }),
  // P26 enhancements
  p26Attribution: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").P26Attribution>("/p26/attribution", { symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m" }),
  p26Calibration: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").P26Calibration>("/p26/calibration", { symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m" }),
  p26Quality: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").P26Quality>("/p26/quality", { symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m" }),
  p26Audit: (params: { symbol?: string; market?: string; timeframe?: string; limit?: number }) =>
    get<import("./types").P26Audit>("/p26/audit", { symbol: params.symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m", limit: params.limit ?? 50 }),
  p26Memory: (symbol: string, params: { market?: string; timeframe?: string }) =>
    get<import("./types").P26Memory>("/p26/memory", { symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m" }),
  p26Regime: (symbol: string, params: { market?: string; timeframe?: string; limit?: number }) =>
    get<import("./types").P26Regime>("/p26/regime", { symbol, market: params.market ?? "crypto", timeframe: params.timeframe ?? "15m", limit: params.limit ?? 200 }),
  p26AlertsCenter: (params: { limit?: number }) =>
    get<import("./types").P26AlertsCenter>("/p26/alerts-center", { limit: params.limit ?? 40 }),
};
