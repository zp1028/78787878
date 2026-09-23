import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import Overview from "./views/Overview";
import Markets from "./views/Markets";
import Detail from "./views/Detail";
import Reports from "./views/Reports";
import Alerts from "./views/Alerts";
import System from "./views/System";
import { api } from "./api";
import type { MarketRow, ProviderHealth, RuntimeStatus, MarketCapabilitiesResponse, MarketCoverageResponse } from "./types";
import { marketLabel } from "./format";

interface AppState {
  backendOnline: boolean;
  runtime?: RuntimeStatus;
  providerHealth: ProviderHealth[];
  capabilities?: MarketCapabilitiesResponse;
  coverage?: MarketCoverageResponse;
  markets: MarketRow[];
  marketCategory: string;
  loadingMarkets: boolean;
  favorites: Set<string>;
  refreshTick: number;
  loadMarkets: (market: string, q?: string, offset?: number) => Promise<void>;
  toggleFavorite: (symbol: string) => void;
}

const Ctx = createContext<AppState | null>(null);
export const useApp = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("AppContext missing");
  return ctx;
};

const NAV_ITEMS = [
  { path: "/", icon: "📊", label: "总览" },
  { path: "/markets", icon: "📈", label: "市场" },
  { path: "/reports", icon: "📋", label: "报告中心" },
  { path: "/alerts", icon: "🔔", label: "预警中心" },
  { path: "/system", icon: "🛠️", label: "系统" },
];

const FAV_KEY = "smart-trader-favorites";

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

export default function App() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeStatus | undefined>();
  const [providerHealth, setProviderHealth] = useState<ProviderHealth[]>([]);
  const [capabilities, setCapabilities] = useState<MarketCapabilitiesResponse | undefined>();
  const [coverage, setCoverage] = useState<MarketCoverageResponse | undefined>();
  const [markets, setMarkets] = useState<MarketRow[]>([]);
  const [marketCategory, setMarketCategory] = useState("crypto");
  const [loadingMarkets, setLoadingMarkets] = useState(false);
  const [favorites, setFavorites] = useState<Set<string>>(loadFavorites);
  const [refreshTick, setRefreshTick] = useState(0);

  const loadMarkets = useCallback(async (market: string, q?: string, offset = 0) => {
    setLoadingMarkets(true);
    setMarketCategory(market);
    try {
      const res = await api.markets({ market, q: q || undefined, limit: 200, offset });
      if (offset === 0) {
        setMarkets(res.markets);
      } else {
        setMarkets((prev) => {
          const seen = new Set(prev.map((m) => m.symbol));
          return [...prev, ...res.markets.filter((m) => !seen.has(m.symbol))];
        });
      }
    } catch (e) {
      console.error("markets load failed", e);
    } finally {
      setLoadingMarkets(false);
    }
  }, []);

  const toggleFavorite = useCallback((symbol: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      try {
        localStorage.setItem(FAV_KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Bootstrap: backend health + universe + periodic refresh
  useEffect(() => {
    let alive = true;
    const bootstrap = async () => {
      const [rt, health, caps, cov] = await Promise.allSettled([
        api.runtimeStatus(),
        api.providerHealth(),
        api.marketCapabilities(),
        api.marketCoverage(),
      ]);
      if (!alive) return;
      if (rt.status === "fulfilled") setRuntime(rt.value);
      if (health.status === "fulfilled") setProviderHealth(health.value.providers);
      if (caps.status === "fulfilled") setCapabilities(caps.value);
      if (cov.status === "fulfilled") setCoverage(cov.value);
      setBackendOnline(rt.status === "fulfilled");
    };
    bootstrap();
    const t = setInterval(() => setRefreshTick((x) => x + 1), 20000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  // Initial market universe load
  useEffect(() => {
    loadMarkets("crypto");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Ctx.Provider
      value={{
        backendOnline,
        runtime,
        providerHealth,
        capabilities,
        coverage,
        markets,
        marketCategory,
        loadingMarkets,
        favorites,
        refreshTick,
        loadMarkets,
        toggleFavorite,
      }}
    >
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <h1>
              Smart<span>Trader</span>
            </h1>
            <p>智能交易分析工作台</p>
          </div>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? "active" : ""}`}
              onClick={() => navigate(item.path)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
          <div className="sidebar-footer">
            <div>
              后端状态：{backendOnline ? <span className="bull-text">在线</span> : <span className="bear-text">离线</span>}
            </div>
            <div style={{ marginTop: 4 }}>只读分析 · 不执行交易</div>
          </div>
        </aside>
        <main className="main-area">
          <StatusBar />
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/system" element={<System />} />
            <Route path="/symbol/:symbol" element={<Detail />} />
          </Routes>
          <div className="disclaimer">
            本报告由智能系统生成，仅供信息参考，不构成投资建议。市场有风险，决策需谨慎。本产品只读分析行情与情景，不执行任何交易，不代管资金。
          </div>
        </main>
      </div>
    </Ctx.Provider>
  );
}

function StatusBar() {
  const { backendOnline, runtime, providerHealth, marketCategory, markets } = useApp();
  const dot = backendOnline ? "online" : "offline";
  const liveProviders = providerHealth.filter((p) => p.available).length;
  return (
    <div className="status-bar">
      <span>
        <span className={`status-dot ${dot}`} />
        {backendOnline ? "后端在线" : "后端离线"}
      </span>
      {runtime && <span>API v{runtime.version}</span>}
      {runtime && (
        <span>
          网关：{runtime.crypto_gateway.providers.join(" → ")}
        </span>
      )}
      <span>
        数据源：{liveProviders}/{providerHealth.length} UP
      </span>
      <span>
        {marketLabel(marketCategory)} · {markets.length} 个品种已载入
      </span>
      <span className="grow" />
      <span className="muted">只读分析终端 · 实时行情 {backendOnline ? "●" : "○"}</span>
    </div>
  );
}
