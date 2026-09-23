import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../App";
import { Chip, Badge, Card, PctCell } from "../components";
import { fmtPrice, fmtCompact, MARKET_TABS } from "../format";
import type { MarketRow } from "../types";

export default function Markets() {
  const { markets, marketCategory, loadMarkets, loadingMarkets, favorites, toggleFavorite, refreshTick, backendOnline } = useApp();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("change");
  const [filter, setFilter] = useState("all");
  const [offset, setOffset] = useState(0);

  const load = (market: string, q: string) => {
    setOffset(0);
    loadMarkets(market, q || undefined, 0);
  };

  useEffect(() => {
    // periodic refresh (every refreshTick) — re-pull current category
    const t = setTimeout(() => {
      loadMarkets(marketCategory, query || undefined, 0);
    }, 15000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick]);

  const filtered = useMemo(() => {
    let list = markets;
    if (query) {
      const q = query.toLowerCase();
      list = list.filter((m) => m.symbol.toLowerCase().includes(q) || (m.name || "").toLowerCase().includes(q));
    }
    if (filter === "gainers") list = list.filter((m) => (m.change_pct ?? 0) > 0);
    else if (filter === "losers") list = list.filter((m) => (m.change_pct ?? 0) < 0);
    else if (filter === "active") list = list.filter((m) => (m.quote_volume ?? 0) > 0).sort((a, b) => (b.quote_volume ?? 0) - (a.quote_volume ?? 0));
    else if (filter === "favorites") list = list.filter((m) => favorites.has(m.symbol));
    if (sort === "change") list = [...list].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
    else if (sort === "price") list = [...list].sort((a, b) => (b.price ?? 0) - (a.price ?? 0));
    else if (sort === "volume") list = [...list].sort((a, b) => (b.quote_volume ?? 0) - (a.quote_volume ?? 0));
    return list;
  }, [markets, query, sort, filter, favorites]);

  return (
    <div>
      <div className="row-between mb-14 wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>市场</h1>
          <div className="muted">完整市场扫描 · 只读分析 · {markets.length} 个品种已载入</div>
        </div>
        {backendOnline ? <Badge tone="accent">ONLINE</Badge> : <Badge tone="warn">OFFLINE</Badge>}
      </div>

      <Card>
        <div className="row wrap mb-14">
          {MARKET_TABS.map((t) => (
            <Chip key={t.key} active={marketCategory === t.key} onClick={() => load(t.key, query)}>
              {t.label}
            </Chip>
          ))}
        </div>
        <input
          className="search-input"
          placeholder="搜索全部品种 / 公司名称"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOffset(0);
            loadMarkets(marketCategory, e.target.value || undefined, 0);
          }}
        />
        <div className="row wrap mt-14">
          {[
            ["change", "涨跌幅"],
            ["price", "价格"],
            ["volume", "成交额"],
          ].map(([k, l]) => (
            <Chip key={k} active={sort === k} onClick={() => setSort(k)}>
              {l}
            </Chip>
          ))}
          {[
            ["all", "全部"],
            ["gainers", "上涨"],
            ["losers", "下跌"],
            ["active", "活跃"],
            ["favorites", "自选"],
          ].map(([k, l]) => (
            <Chip key={k} active={filter === k} onClick={() => setFilter(k)}>
              {l}
            </Chip>
          ))}
        </div>
      </Card>

      {!backendOnline && (
        <div className="error-box">
          市场数据服务不可达。请在「系统」页检查后端连接与 Provider 状态；此页面不会生成模拟币种或价格。
        </div>
      )}

      <Card title={`品种列表`} sub={`${filtered.length} 个匹配`} right={loadingMarkets ? <Badge tone="accent">刷新中…</Badge> : undefined}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 34 }} />
              <th>品种 / 市场</th>
              <th className="th-num">最新价</th>
              <th className="th-num">24H 涨跌</th>
              <th className="th-num">24H 成交额</th>
              <th className="th-num">成交笔数</th>
              <th style={{ textAlign: "right" }}>状态</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => (
              <MarketRowTable
                key={m.symbol}
                m={m}
                fav={favorites.has(m.symbol)}
                onToggleFav={() => toggleFavorite(m.symbol)}
                onOpen={() => navigate(`/symbol/${m.symbol}`)}
              />
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7}>
                  <div className="empty">当前没有匹配的实时品种；只有真实 provider 返回后才会进入列表。</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {filtered.length >= 200 && (
          <div className="mt-14" style={{ textAlign: "center" }}>
            <button
              className="chip"
              onClick={() => {
                const next = offset + 200;
                setOffset(next);
                loadMarkets(marketCategory, query || undefined, next);
              }}
            >
              加载更多 · 当前 {markets.length} 个
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

function MarketRowTable({ m, fav, onToggleFav, onOpen }: { m: MarketRow; fav: boolean; onToggleFav: () => void; onOpen: () => void }) {
  return (
    <tr onClick={onOpen}>
      <td onClick={(e) => { e.stopPropagation(); onToggleFav(); }} style={{ cursor: "pointer", textAlign: "center" }}>
        <span style={{ color: fav ? "#4fc3f7" : "#6b7688", fontSize: 15 }}>{fav ? "★" : "☆"}</span>
      </td>
      <td>
        <div className="strong">{m.symbol}</div>
        <div className="muted" style={{ fontSize: 11 }}>
          {m.name} · {m.venue || m.market?.toUpperCase()}
          {(m.market_data_type || m.contract_type) && (
            <span className="accent-text" style={{ marginLeft: 5 }}>
              {m.contract_type || m.market_data_type}
            </span>
          )}
        </div>
      </td>
      <td className="num strong">{fmtPrice(m.price)}</td>
      <td className="num"><PctCell value={m.change_pct} /></td>
      <td className="num secondary">{fmtCompact(m.quote_volume)}</td>
      <td className="num muted">{fmtCompact(m.trades)}</td>
      <td style={{ textAlign: "right" }}>
        {m.quote_status === "live" ? <Badge tone="bull">实时</Badge> : <Badge tone="warn">{m.quote_status || "等待"}</Badge>}
      </td>
    </tr>
  );
}
