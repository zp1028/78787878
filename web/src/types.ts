// Smart Trader Web — API data contracts (mirrors backend /api/v1 responses)

export interface MarketRow {
  symbol: string;
  name: string;
  market: string;
  asset_type?: string;
  venue?: string;
  currency?: string;
  price?: number | null;
  previous_close?: number | null;
  change_pct?: number | null;
  volume?: number | null;
  quote_volume?: number | null;
  trades?: number | null;
  source?: string;
  market_data_type?: string;
  contract_type?: string;
  bid?: number | null;
  bid_size?: number | null;
  ask?: number | null;
  ask_size?: number | null;
  mark_price?: number | null;
  index_price?: number | null;
  funding_rate?: number | null;
  quote_status?: string;
  analysis_only?: boolean;
}

export interface MarketsResponse {
  analysis_only: boolean;
  count: number;
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  markets: MarketRow[];
}

export interface Candle {
  open_time: number;
  close_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed?: boolean;
}

export interface CandlesResponse {
  symbol: string;
  market: string;
  timeframe: string;
  count: number;
  stale: boolean;
  provider: string;
  realtime: boolean;
  data_time?: number;
  candles: Candle[];
}

export interface IndicatorReport {
  instrument_id: string;
  symbol: string;
  market: string;
  timeframe: string;
  bars: number;
  last_price: number;
  last_close_time: number;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  ema_12?: number | null;
  ema_26?: number | null;
  rsi_14?: number | null;
  stoch_k?: number | null;
  stoch_d?: number | null;
  stoch_rsi?: number | null;
  cci_20?: number | null;
  williams_r?: number | null;
  ultimate_osc?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_hist?: number | null;
  adx?: number | null;
  bb_upper?: number | null;
  bb_middle?: number | null;
  bb_lower?: number | null;
  trend?: string;
  trend_strength?: string;
  oversold?: string[];
  overbought?: string[];
  signals?: string[];
  summary?: string;
  narrative?: string;
  data_quality?: string;
  generated_at?: number;
}

export interface StructureResponse {
  data_contract: string;
  analysis_only: boolean;
  read_only: boolean;
  symbol: string;
  market: string;
  timeframe: string;
  available: boolean;
  last_price?: number;
  support?: number;
  resistance?: number;
  trend?: string;
  breakout?: string;
  pivots?: { index: number; price: number; type: string }[];
  note?: string;
  swing_high?: number;
  swing_low?: number;
  generated_at?: number;
}

export interface ScenarioAnalysis {
  data_contract: string;
  analysis_only: boolean;
  read_only: boolean;
  available: boolean;
  symbol: string;
  market: string;
  timeframe: string;
  generated_at?: number;
  data_timestamp?: number;
  last_price?: number;
  trend?: string;
  rsi?: number;
  macd_hist?: number;
  adx?: number;
  volume_ratio?: number;
  market_structure?: {
    trend?: string;
    support?: number;
    resistance?: number;
    swing_high?: number;
    swing_low?: number;
    note?: string;
  };
  scenarios?: Scenario[];
  recommendation?: string;
  entry_zone?: string;
  stop_loss?: number;
  targets?: number[];
  confidence?: number;
  risk_reward?: number;
  summary?: string;
  narrative?: string;
  holding?: {
    direction?: string;
    entry_price?: number;
    current_price?: number;
    unrealized_pnl_pct?: number;
    advice?: string;
    suggested_stop?: number;
    suggested_targets?: number[];
  } | null;
}

export interface Scenario {
  name: string;
  direction: "long" | "short" | "neutral";
  probability: number;
  description: string;
  key_levels?: { level: string; price?: number; note?: string }[];
  conditions?: string[];
}

export interface RiskMapResponse {
  data_contract: string;
  analysis_only: boolean;
  read_only: boolean;
  symbol: string;
  market: string;
  current_timeframe: string;
  last_price?: number;
  timeframes: Record<
    string,
    {
      available: boolean;
      trend?: string;
      support?: number;
      resistance?: number;
      breakout?: string;
      risk?: string;
      note?: string;
    }
  >;
  overall_risk?: string;
  summary?: string;
  generated_at?: number;
}

export interface UnifiedReport {
  symbol: string;
  market: string;
  timeframe: string;
  generated_at: string;
  last_price?: number;
  last_close_time?: number;
  trend?: string;
  trend_strength?: string;
  structure?: {
    state?: string;
    note?: string;
    swing_high?: number;
    swing_low?: number;
    support?: number[];
    resistance?: number[];
  };
  summary?: string;
  narrative?: string;
  longSummary?: string;
  shortSummary?: string;
  holdingSummary?: string;
  riskNotes?: string[];
  dataTimestamp?: string;
  dataQuality?: string;
  confidence?: number;
  direction?: string;
}

export interface FeedItem {
  symbol: string;
  market: string;
  timeframe: string;
  direction?: string;
  confidence?: number;
  summary?: string;
  narrative?: string;
  trend?: string;
  status?: string;
  generated_at?: number;
  feedbackSummary?: string;
  feedbackState?: string;
  reportId?: string;
  entryZone?: string;
  stopLoss?: number;
  targets?: number[];
  why?: string;
}

export interface AnalysisFeedResponse {
  generated_at: number;
  data_quality?: string;
  items: FeedItem[];
}

export interface FeedbackHistoryItem {
  reportId?: string;
  direction?: string;
  confidence?: number;
  feedbackSummary?: string;
  feedbackState?: string;
  timestamp?: number;
}

export interface AnalysisFeedbackResponse {
  symbol: string;
  market: string;
  timeframe: string;
  currentState?: string;
  currentSummary?: string;
  priceAtReport?: number;
  currentPrice?: number;
  history?: FeedbackHistoryItem[];
  generated_at?: number;
}

export interface ReportCatalogItem {
  id: number;
  key: string;
  name: string;
  domain: string;
  priority: string;
  update: string;
  markets: string[];
  source_requirements: string[];
  output: string[];
}

export interface ReportCatalogResponse {
  count: number;
  reports: ReportCatalogItem[];
}

export interface ProviderHealth {
  name: string;
  available: boolean;
  status: string;
  message: string;
}

export interface ProviderHealthResponse {
  order: string[];
  providers: ProviderHealth[];
}

export interface RuntimeStatus {
  status: string;
  version: string;
  server_time_ms: number;
  crypto_gateway: {
    providers: string[];
    source: string;
    market_endpoint: string;
    provider_health_endpoint: string;
  };
}

export interface MarketCapability {
  market: string;
  provider: string;
  universe_discovery?: boolean;
  quote?: boolean;
  candles?: boolean;
  realtime?: boolean;
  derivatives?: boolean;
  available?: boolean;
  missing?: string[];
}

export interface MarketCapabilitiesResponse {
  generated_at: number;
  analysis_only: boolean;
  markets: Record<string, MarketCapability>;
}

export interface MarketCoverageItem {
  count?: number;
  universe?: string;
  realtime?: boolean;
  quote_note?: string;
  configured?: boolean;
  provider_order?: string[];
}

export interface MarketCoverageResponse {
  generated_at?: number;
  total?: number;
  markets: Record<string, number | MarketCoverageItem>;
}

export interface DerivativesResponse {
  symbol: string;
  provider?: string;
  available?: boolean;
  read_only?: boolean;
  funding?: {
    latest?: { fundingRate?: number; provider?: string } | null;
    history?: unknown[];
  };
  open_interest?: {
    latest?: { open_interest?: number; provider?: string } | null;
    history?: unknown[];
  };
  mark_index?: {
    available?: boolean;
    mark_price?: number | null;
    index_price?: number | null;
    last_funding_rate?: number | null;
    provider?: string | null;
  } | null;
  long_short?: { latest?: unknown; history?: unknown[] };
  taker_flow?: { latest?: unknown; history?: unknown[] };
  basis?: { latest?: unknown; history?: unknown[] };
  liquidations?: { latest?: unknown; history?: unknown[] };
  capabilities?: Record<string, boolean>;
}

export interface MultiExchangeResponse {
  symbol: string;
  normalized_symbol: string;
  read_only: boolean;
  providers: {
    provider: string;
    available: boolean;
    mark_price?: number | null;
    index_price?: number | null;
    funding_rate?: number | null;
    open_interest?: number | null;
    reason?: string;
  }[];
  available_provider_count: number;
  consensus?: {
    mark_price_mean?: number | null;
    funding_rate_mean?: number | null;
    open_interest_mean?: number | null;
  };
  divergence?: {
    funding_rate_spread?: number | null;
    mark_price_spread_pct?: number | null;
  };
  analysis_only: boolean;
}

export interface TerminalResponse {
  analysis_only: boolean;
  symbol: string;
  provider: string;
  market_data_type: string;
  server_time: number;
  quote: {
    last_price?: number | null;
    price_change?: number | null;
    change_pct?: number | null;
    high_24h?: number | null;
    low_24h?: number | null;
    volume?: number | null;
    quote_volume?: number | null;
    trades?: number | null;
    data_time?: number | null;
  };
  mark?: {
    mark_price?: number | null;
    index_price?: number | null;
    funding_rate?: number | null;
    next_funding_time?: number | null;
    data_time?: number | null;
  };
  book?: {
    bid?: number | null;
    bid_size?: number | null;
    ask?: number | null;
    ask_size?: number | null;
    data_time?: number | null;
  };
  depth?: {
    last_update_id?: number | null;
    bids: { price: number; qty: number }[];
    asks: { price: number; qty: number }[];
  };
  trades?: { id?: number; price?: number; qty?: number; buyer_maker?: boolean; time?: number }[];
  candles?: { open_time: number; open: number; high: number; low: number; close: number; volume: number; close_time: number }[];
  freshness?: {
    quote_ms?: number | null;
    mark_ms?: number | null;
    book_ms?: number | null;
    status?: string;
  };
}

export interface InstrumentAnalysisSnapshot {
  symbol: string;
  market: string;
  provider?: string;
  timeframe?: string;
  snapshotAvailable?: boolean;
  capabilityStatus?: string;
  realtime?: boolean;
  quality?: string;
  missing?: string[];
  generated_at?: number;
}

export interface InstrumentSnapshot {
  symbol: string;
  market: string;
  provider?: string;
  realtime?: boolean;
  data_time?: number;
  stale?: boolean;
  candle_count?: number;
  snapshots?: Record<string, unknown>;
}

// ---- P26 enhancement payloads ----
export interface P26Attribution {
  symbol: string; market: string; timeframe: string;
  resolved_count: number; total_count: number; accuracy_pct: number | null;
  sample_note: string;
  state_counts: Record<string, number>; reasons: Record<string, number>;
  direction_stats?: {
    direction: string; total: number; validated: number; invalidated: number;
    tracking: number; waiting: number; accuracy_pct: number | null;
  }[];
  multi_scenario_note?: string;
}
export interface P26Calibration {
  symbol: string; market: string; timeframe: string;
  sample_count: number; brier_score: number | null; calibrated: boolean; note: string;
}
export interface P26Quality {
  symbol: string; market: string; timeframe: string;
  score: number; grade: string;
  checks: { check: string; ok: boolean; points: number }[];
  quality_note: string;
}
export interface P26AuditItem {
  report_id: string; sha256: string; parent_report_id: string | null; version: number;
  symbol: string; market: string; timeframe: string; direction: string;
  confidence: number | null; generated_at: number; created_at: number;
}
export interface P26Audit { count: number; immutable: boolean; items: P26AuditItem[]; }
export interface P26Memory {
  symbol: string; market: string; timeframe: string;
  current_fingerprint: Record<string, unknown> | null;
  situation_count: number;
  similar_situation: { count: number; validated: number; invalidated: number; tracking: number } | null;
  note: string;
}
export interface P26Regime {
  symbol: string; market: string; timeframe: string;
  regime: string; trend: string; volatility: string;
  atr_pct: number; sma_slope_pct: number; detail: string;
}

export interface P26AlertsCenter {
  auto_alerts: {
    symbol: string; name: string; venue: string; level: "P0" | "P1" | "P2";
    kind: string; messages: string[]; change_pct: number;
    price?: number | null; quote_volume?: number | null;
  }[];
  user_alerts: { id: number; symbol: string; kind: string; operator: string; threshold: number; enabled: boolean }[];
  level_counts: Record<string, number>;
  merge_note: string;
  generated_at: number;
  read_only: boolean;
}
