import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../App";
import { api } from "../api";
import { Card, StatCard, Badge, MarketRowItem, ConfidenceBar, DirectionBadge } from "../components";
import { fmtPrice, fmtPct, fmtCompact, fmtTime, marketLabel } from "../format";
import type { AnalysisFeedResponse, FeedItem, MarketRow } from "../types";

export default function Overview() {
  const { markets, favorites, backendOnline, refreshTick } = useApp();
  const navigate = useNavigate();
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [feedLoading, setFeedLoading] = useState(false);
  const [preference, setPreference] = useState<string>(() => {
    try {
      return localStorage.getItem("smart-trader-preference") || "balanced";
    } catch {
      return "balanced";
    }
  });
  const [favFirst, setFavFirst] = useState<boolean>(() => {
    try {
      return localStorage.getItem("smart-trader-fav-first") !== "0";
    } catch {
      return true;
    }
  });

  const savePreference = (v: string) => {
    setPreference(v);
    localStorage.setItem("smart-trader-preference", v);
  };
  const saveFavFirst = (v: boolean) => {
    setFavFirst(v);
    localStorage.setItem("smart-trader-fav-first", v ? "1" : "0");
  };

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setFeedLoading(true);
      try {
        const res = await api.analysisFeed({ market: "crypto", limit: 8 });
        if (alive) setFeed(res.items ?? []);
      } catch {
        /* keep previous */
      } finally {
        if (alive) setFeedLoading(false);
      }
    };
    load();
    return () => {
      alive = false;
    };
  }, [refreshTick]);

  // Personalized feed: favorites first, then risk-preference weighting.
  const preferenceBoost = (symbol: string): number => {
    const m = markets.find((x) => x.symbol === symbol);
    const chg = Math.abs(m?.change_pct ?? 0);
    const vol = m?.quote_volume ?? 0;
    if (preference === "aggressive") return (chg > 4 ? 10 : 0) + (vol > 50_000_000 ? 5 : 0);
    if (preference === "conservative") return chg < 1.5 ? 8 : 0;
    return chg < 3 ? 3 : 0;
  };
  const personalized = [...feed].sort((a, b) => {
    const fa = favorites.has(a.symbol) ? 1 : 0;
    const fb = favorites.has(b.symbol) ? 1 : 0;
    if (favFirst && fa !== fb) return fb - fa;
    return preferenceBoost(b.symbol) - preferenceBoost(a.symbol);
  });

  const sorted = [...markets].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
  const topGainers = sorted.slice(0, 5);
  const topLosers = [...sorted].sort((a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0)).slice(0, 5);
  const active = [...markets].sort((a, b) => (b.quote_volume ?? 0) - (a.quote_volume ?? 0)).slice(0, 6);
  const favs = markets.filter((m) => favorites.has(m.symbol)).slice(0, 6);

  const upCount = markets.filter((m) => (m.change_pct ?? 0) > 0).length;
  const downCount = markets.filter((m) => (m.change_pct ?? 0) < 0).length;
  const totalVol = markets.reduce((s, m) => s + (m.quote_volume ?? 0), 0);

  return (
    <div>
      <div className="row-between mb-14 wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>发现</h1>
          <div className="muted">实时行情 → 信号 → 分析报告 · 历史报告冻结，后续行情单独反馈</div>
        </div>
        {backendOnline ? <Badge tone="accent">ANALYSIS ENGINE ONLINE</Badge> : <Badge tone="warn">DATA ONLY</Badge>}
      </div>

      <Card
        title="高置信度分析"
        sub={`15m 周期 · 置信度 ≥ 75% 进入推荐 · ${preference === "aggressive" ? "激进偏好" : preference === "conservative" ? "保守偏好" : "均衡偏好"}`}
        right={
          <div className="row" style={{ gap: 6 }}>
            <button
              onClick={() => savePreference("conservative")}
              style={{ padding: "3px 8px", fontSize: 11, borderRadius: 5, cursor: "pointer", border: "1px solid var(--border)", background: preference === "conservative" ? "var(--accent-soft)" : "var(--bg-soft)", color: "var(--text)" }}
            >
              保守
            </button>
            <button
              onClick={() => savePreference("balanced")}
              style={{ padding: "3px 8px", fontSize: 11, borderRadius: 5, cursor: "pointer", border: "1px solid var(--border)", background: preference === "balanced" ? "var(--accent-soft)" : "var(--bg-soft)", color: "var(--text)" }}
            >
              均衡
            </button>
            <button
              onClick={() => savePreference("aggressive")}
              style={{ padding: "3px 8px", fontSize: 11, borderRadius: 5, cursor: "pointer", border: "1px solid var(--border)", background: preference === "aggressive" ? "var(--accent-soft)" : "var(--bg-soft)", color: "var(--text)" }}
            >
              激进
            </button>
            <button
              onClick={() => saveFavFirst(!favFirst)}
              style={{ padding: "3px 8px", fontSize: 11, borderRadius: 5, cursor: "pointer", border: "1px solid var(--border)", background: favFirst ? "var(--accent-soft)" : "var(--bg-soft)", color: "var(--text)" }}
            >
              {favFirst ? "自选优先 ✓" : "自选优先"}
            </button>
          </div>
        }
      >
        {feedLoading && <div className="loading-bar" />}
        {!feedLoading && feed.length === 0 && (
          <div className="empty">
            {backendOnline
              ? "分析引擎正在积累行情数据并产生有效报告…请稍后刷新"
              : "Smart Trader 后端未连接；行情与分析数据不会伪造或改走交易所直连。"}
          </div>
        )}
        {personalized.map((item) => (
          <div key={item.symbol} className="feed-item" onClick={() => navigate(`/symbol/${item.symbol}`)}>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="row">
                <span className="sym">{item.symbol}</span>
                <DirectionBadge direction={item.direction} />
                {item.status && <span className="muted" style={{ fontSize: 11 }}>{item.status}</span>}
              </div>
              {item.summary && <div className="summary">{item.summary}</div>}
              {item.why && <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>↑ {item.why}</div>}
              {item.feedbackSummary && (
                <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>
                  反馈：{item.feedbackSummary}
                </div>
              )}
            </div>
            <div style={{ textAlign: "right", minWidth: 130 }}>
              <ConfidenceBar value={item.confidence} />
              {item.entryZone && <div className="muted mono" style={{ fontSize: 11, marginTop: 4 }}>入场 {item.entryZone}</div>}
              {item.stopLoss != null && <div className="muted mono" style={{ fontSize: 11 }}>止损 {fmtPrice(item.stopLoss)}</div>}
            </div>
          </div>
        ))}
      </Card>

      <div className="grid grid-3 mb-14">
        <StatCard label="已载入品种" value={markets.length} note="当前市场页" />
        <StatCard label="上涨 / 下跌" value={<span>{upCount} <span className="muted" style={{ fontSize: 14 }}>/</span> {downCount}</span>} note="24H" />
        <StatCard label="24H 成交额" value={fmtCompact(totalVol)} note="当前市场" tone="accent" />
      </div>

      {favs.length > 0 && (
        <Card title="自选观察" right={<Badge tone="neutral">{favs.length} 个</Badge>}>
          {favs.map((m) => (
            <MarketRowItem key={m.symbol} m={m} onOpen={() => navigate(`/symbol/${m.symbol}`)} />
          ))}
        </Card>
      )}

      <div className="grid grid-2">
        <Card title="强势异动" sub="24H 涨幅领先">
          {topGainers.map((m) => (
            <MarketRowItem key={m.symbol} m={m} onOpen={() => navigate(`/symbol/${m.symbol}`)} />
          ))}
        </Card>
        <Card title="弱势观察" sub="24H 跌幅领先">
          {topLosers.map((m) => (
            <MarketRowItem key={m.symbol} m={m} onOpen={() => navigate(`/symbol/${m.symbol}`)} />
          ))}
        </Card>
      </div>

      <Card title="高关注品种" sub="按 24H 成交额排序" right={<Badge tone="neutral">TOP {active.length}</Badge>}>
        {active.map((m) => (
          <MarketRowItem key={m.symbol} m={m} onOpen={() => navigate(`/symbol/${m.symbol}`)} />
        ))}
        <div className="muted mt-6" style={{ fontSize: 11 }}>
          完整品种搜索、排序、分页请进入「市场」
        </div>
      </Card>
    </div>
  );
}
