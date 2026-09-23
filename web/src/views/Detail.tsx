import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useApp } from "../App";
import { api } from "../api";
import { Card, Badge, Chip, DirectionBadge, ConfidenceBar } from "../components";
import { fmtPrice, fmtPct, fmtNum, fmtCompact, fmtTime, TIMEFRAMES, directionLabel } from "../format";
import {
  renderCandleChart,
  renderRsiChart,
  renderMacdChart,
  renderDonut,
  scenarioDonutData,
  disposeChart,
} from "../charts";
import type {
  Candle,
  IndicatorReport,
  StructureResponse,
  ScenarioAnalysis,
  RiskMapResponse,
  UnifiedReport,
  AnalysisFeedbackResponse,
  DerivativesResponse,
  MultiExchangeResponse,
  InstrumentAnalysisSnapshot,
  P26Attribution,
  P26Calibration,
  P26Quality,
  P26Memory,
  P26Regime,
} from "../types";

export default function Detail() {
  const { symbol = "" } = useParams();
  const navigate = useNavigate();
  const { favorites, toggleFavorite, markets } = useApp();
  const [timeframe, setTimeframe] = useState("15m");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [indicators, setIndicators] = useState<IndicatorReport | null>(null);
  const [structure, setStructure] = useState<StructureResponse | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioAnalysis | null>(null);
  const [riskMap, setRiskMap] = useState<RiskMapResponse | null>(null);
  const [unified, setUnified] = useState<UnifiedReport | null>(null);
  const [feedback, setFeedback] = useState<AnalysisFeedbackResponse | null>(null);
  const [derivatives, setDerivatives] = useState<DerivativesResponse | null>(null);
  const [multiExchange, setMultiExchange] = useState<MultiExchangeResponse | null>(null);
  const [snapshot, setSnapshot] = useState<InstrumentAnalysisSnapshot | null>(null);
  const [p26Attribution, setP26Attribution] = useState<P26Attribution | null>(null);
  const [p26Calibration, setP26Calibration] = useState<P26Calibration | null>(null);
  const [p26Quality, setP26Quality] = useState<P26Quality | null>(null);
  const [p26Memory, setP26Memory] = useState<P26Memory | null>(null);
  const [p26Regime, setP26Regime] = useState<P26Regime | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subChart, setSubChart] = useState<"rsi" | "macd">("rsi");

  const candleRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLDivElement>(null);
  const donutRef = useRef<HTMLDivElement>(null);

  const marketRow = markets.find((m) => m.symbol === symbol || m.symbol.replace("/", "") === symbol);
  const isFav = favorites.has(symbol);
  const symRaw = symbol.toUpperCase().replace("/", "");

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    // Split into two waves to stay well under the browser's ~6 connection
    // limit per origin. Core data first, then the deeper analysis modules.
    try {
      const [c, ind, st, sc] = await Promise.allSettled([
        api.candles(symRaw, { timeframe, market: "crypto", limit: 300 }),
        api.indicators(symRaw, { timeframe, market: "crypto", limit: 300 }),
        api.structure(symRaw, { timeframe, market: "crypto", limit: 200 }),
        api.scenarios(symRaw, { timeframe, market: "crypto", limit: 200 }),
      ]);
      if (c.status === "fulfilled") setCandles(c.value.candles ?? []);
      if (ind.status === "fulfilled") setIndicators(ind.value);
      if (st.status === "fulfilled") setStructure(st.value);
      if (sc.status === "fulfilled") setScenarios(sc.value);

      const [rm, ur, fb, snap] = await Promise.allSettled([
        api.riskMap(symRaw, { timeframe, market: "crypto", limit: 160 }),
        api.unifiedReport(symRaw, { timeframe, market: "crypto", limit: 250 }),
        api.analysisFeedback(symRaw, { market: "crypto", timeframe }),
        api.instrumentAnalysisSnapshot(symRaw, { market: "crypto", timeframe }),
      ]);
      if (rm.status === "fulfilled") setRiskMap(rm.value);
      if (ur.status === "fulfilled") setUnified(ur.value);
      if (fb.status === "fulfilled") setFeedback(fb.value);
      if (snap.status === "fulfilled") setSnapshot(snap.value);
      const failures = [c, ind, st, sc, rm, ur, fb, snap].filter((r) => r.status === "rejected");
      if (failures.length > 0) {
        setError(`${failures.length} 个分析模块暂不可用（数据源受限），核心行情仍可显示。`);
      }
    } finally {
      setLoading(false);
    }
  }, [symRaw, timeframe]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Crypto-only extras
  useEffect(() => {
    if (marketRow?.market !== "crypto" && !marketRow) return;
    let alive = true;
    api.derivatives(symRaw, { period: "1h" }).then((d) => alive && setDerivatives(d)).catch(() => {});
    api.multiExchange(symRaw).then((d) => alive && setMultiExchange(d)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [symRaw, marketRow?.market]);

  // P26 enhancements (third wave: regime / quality / attribution / calibration / memory)
  useEffect(() => {
    if (!symRaw) return;
    let alive = true;
    api.p26Regime(symRaw, { timeframe }).then((d) => alive && setP26Regime(d)).catch(() => {});
    api.p26Quality(symRaw, { timeframe }).then((d) => alive && setP26Quality(d)).catch(() => {});
    api.p26Attribution(symRaw, { timeframe }).then((d) => alive && setP26Attribution(d)).catch(() => {});
    api.p26Calibration(symRaw, { timeframe }).then((d) => alive && setP26Calibration(d)).catch(() => {});
    api.p26Memory(symRaw, { timeframe }).then((d) => alive && setP26Memory(d)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [symRaw, timeframe]);

  // Charts — each render is isolated so one failing chart never breaks the page
  useEffect(() => {
    if (!candleRef.current || candles.length === 0) return;
    try {
      const chart = renderCandleChart(candleRef.current, candles, indicators ?? undefined);
      return () => disposeChart(chart);
    } catch (e) {
      console.error("candle chart error", e);
    }
  }, [candles, indicators]);

  useEffect(() => {
    if (!subRef.current || candles.length === 0) return;
    try {
      const chart = subChart === "rsi" ? renderRsiChart(subRef.current, candles) : renderMacdChart(subRef.current, candles);
      return () => disposeChart(chart);
    } catch (e) {
      console.error("sub chart error", e);
    }
  }, [candles, subChart]);

  useEffect(() => {
    if (!donutRef.current) return;
    const data = scenarioDonutData(scenarios?.scenarios);
    if (!data) return;
    try {
      const chart = renderDonut(donutRef.current, data, scenarios?.confidence != null ? `${scenarios.confidence}%` : "");
      return () => disposeChart(chart);
    } catch (e) {
      console.error("donut chart error", e);
    }
  }, [scenarios]);

  if (!symbol) return null;

  return (
    <div>
      <div className="detail-header">
        <button className="back-btn" onClick={() => navigate(-1)}>
          ← 返回
        </button>
        <div className="grow">
          <div className="row">
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>{symbol.toUpperCase()}</h1>
            {marketRow && (
              <>
                <Badge tone={marketRow.quote_status === "live" ? "bull" : "warn"}>
                  {marketRow.quote_status === "live" ? "实时" : marketRow.quote_status || "等待"}
                </Badge>
                {marketRow.contract_type && <Badge tone="accent">{marketRow.contract_type}</Badge>}
              </>
            )}
          </div>
          <div className="muted">{marketRow?.name} · 只读分析</div>
        </div>
        <button className="back-btn" onClick={() => toggleFavorite(symRaw)}>
          {isFav ? "★ 已自选" : "☆ 加入自选"}
        </button>
      </div>

      {/* Price header */}
      {marketRow && (
        <Card>
          <div className="row-between wrap">
            <div>
              <div className="mono" style={{ fontSize: 30, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                {fmtPrice(marketRow.price)}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                {marketRow.name} · {marketRow.venue || marketRow.market?.toUpperCase()} · 24H 成交 {fmtCompact(marketRow.quote_volume)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className={((marketRow.change_pct ?? 0) >= 0 ? "bull-text" : "bear-text")} style={{ fontSize: 22, fontWeight: 700 }}>
                {fmtPct(marketRow.change_pct)}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                买 {fmtPrice(marketRow.bid)} · 卖 {fmtPrice(marketRow.ask)}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Timeframe */}
      <div className="row-between mb-14 wrap">
        <div className="timeframe-bar">
          {TIMEFRAMES.map((tf) => (
            <Chip key={tf} active={timeframe === tf} onClick={() => setTimeframe(tf)}>
              {tf}
            </Chip>
          ))}
        </div>
        {loading && <span className="muted" style={{ fontSize: 12 }}>分析加载中…</span>}
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* Candles + indicators */}
      <Card title="价格与成交量" sub={`${timeframe} K线 · MA20 / MA50 · 布林带`} right={<Badge tone="neutral">{candles.length} 根</Badge>}>
        <div ref={candleRef} className="chart-box chart-lg" />
        {candles.length === 0 && <div className="empty">等待 K 线数据…</div>}
      </Card>

      <Card
        title={subChart === "rsi" ? "RSI(14)" : "MACD"}
        sub="技术指标副图"
        right={
          <div className="row">
            <Chip active={subChart === "rsi"} onClick={() => setSubChart("rsi")}>RSI</Chip>
            <Chip active={subChart === "macd"} onClick={() => setSubChart("macd")}>MACD</Chip>
          </div>
        }
      >
        <div ref={subRef} className="chart-box chart-md" />
      </Card>

      <div className="grid grid-2">
        {/* Market structure */}
        <Card title="市场结构" sub={structure ? `${structure.timeframe} · ${structure.trend ?? "—"}` : undefined}>
          {structure?.available ? (
            <div className="kv">
              <div className="item">
                <div className="k">趋势</div>
                <div className="v">{structure.trend ?? "—"}</div>
              </div>
              <div className="item">
                <div className="k">支撑</div>
                <div className="v bull-text">{fmtPrice(structure.support)}</div>
              </div>
              <div className="item">
                <div className="k">阻力</div>
                <div className="v bear-text">{fmtPrice(structure.resistance)}</div>
              </div>
              <div className="item">
                <div className="k">突破</div>
                <div className="v">{structure.breakout ?? "—"}</div>
              </div>
              <div className="item">
                <div className="k">波段高</div>
                <div className="v">{fmtPrice(structure.swing_high)}</div>
              </div>
              <div className="item">
                <div className="k">波段低</div>
                <div className="v">{fmtPrice(structure.swing_low)}</div>
              </div>
            </div>
          ) : (
            <div className="empty">结构数据暂不可用</div>
          )}
          {structure?.note && <div className="muted mt-10" style={{ fontSize: 12 }}>{structure.note}</div>}
        </Card>

        {/* Indicator snapshot */}
        <Card title="指标快照" sub={indicators ? `${indicators.timeframe} · ${indicators.trend ?? ""}` : undefined}>
          {indicators ? (
            <div className="kv">
              <div className="item">
                <div className="k">RSI(14)</div>
                <div className={`v ${(indicators.rsi_14 ?? 50) >= 70 ? "bear-text" : (indicators.rsi_14 ?? 50) <= 30 ? "bull-text" : ""}`}>
                  {indicators.rsi_14?.toFixed(1) ?? "—"}
                </div>
              </div>
              <div className="item">
                <div className="k">MACD</div>
                <div className="v">{indicators.macd?.toFixed(2) ?? "—"}</div>
              </div>
              <div className="item">
                <div className="k">MACD 柱</div>
                <div className={`v ${(indicators.macd_hist ?? 0) >= 0 ? "bull-text" : "bear-text"}`}>
                  {indicators.macd_hist?.toFixed(2) ?? "—"}
                </div>
              </div>
              <div className="item">
                <div className="k">ADX</div>
                <div className="v">{indicators.adx?.toFixed(1) ?? "—"}</div>
              </div>
              <div className="item">
                <div className="k">KDJ K/D</div>
                <div className="v">
                  {indicators.stoch_k?.toFixed(0)} / {indicators.stoch_d?.toFixed(0)}
                </div>
              </div>
              <div className="item">
                <div className="k">布林带</div>
                <div className="v mono" style={{ fontSize: 12 }}>
                  {fmtPrice(indicators.bb_lower)} ~ {fmtPrice(indicators.bb_upper)}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty">指标数据暂不可用</div>
          )}
          {indicators?.summary && <div className="secondary mt-10" style={{ fontSize: 12 }}>{indicators.summary}</div>}
        </Card>
      </div>

      {/* Scenarios with donut */}
      <Card title="多空情景" sub={scenarios ? `${scenarios.timeframe} · ${scenarios.trend ?? ""}` : undefined}>
        {scenarios?.available ? (
          <div className="grid grid-2">
            <div ref={donutRef} className="chart-box" style={{ height: 220 }} />
            <div>
              {scenarios.scenarios?.map((s) => (
                <div key={s.name} className="feed-item" style={{ borderBottom: "1px solid var(--border-soft)" }}>
                  <div className="grow">
                    <div className="row">
                      <DirectionBadge direction={s.direction} />
                      <span className="strong">{s.name}</span>
                    </div>
                    <div className="summary">{s.description}</div>
                    {s.key_levels && (
                      <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                        {s.key_levels.map((k) => `${k.level}${k.price ? " " + fmtPrice(k.price) : ""}`).join(" · ")}
                      </div>
                    )}
                  </div>
                  <div className="mono strong" style={{ fontSize: 16, color: "#4fc3f7" }}>
                    {s.probability}%
                  </div>
                </div>
              ))}
              {scenarios.entry_zone && (
                <div className="mt-10 kv">
                  <div className="item">
                    <div className="k">入场区间</div>
                    <div className="v" style={{ fontSize: 13 }}>{scenarios.entry_zone}</div>
                  </div>
                  {scenarios.stop_loss != null && (
                    <div className="item">
                      <div className="k">止损</div>
                      <div className="v bear-text" style={{ fontSize: 13 }}>{fmtPrice(scenarios.stop_loss)}</div>
                    </div>
                  )}
                  {scenarios.targets && scenarios.targets.length > 0 && (
                    <div className="item">
                      <div className="k">目标</div>
                      <div className="v" style={{ fontSize: 13 }}>{scenarios.targets.map((t) => fmtPrice(t)).join(" / ")}</div>
                    </div>
                  )}
                  {scenarios.risk_reward != null && (
                    <div className="item">
                      <div className="k">盈亏比</div>
                      <div className="v" style={{ fontSize: 13 }}>1:{scenarios.risk_reward.toFixed(1)}</div>
                    </div>
                  )}
                </div>
              )}
              {scenarios.summary && <div className="secondary mt-10" style={{ fontSize: 12 }}>{scenarios.summary}</div>}
            </div>
          </div>
        ) : (
          <div className="empty">情景分析暂不可用</div>
        )}
      </Card>

      {/* Unified report */}
      {unified && (
        <Card
          title="实时分析结论"
          sub={`${unified.timeframe} · 数据质量 ${unified.dataQuality ?? "—"}`}
          right={unified.direction ? <DirectionBadge direction={unified.direction} /> : undefined}
        >
          <div className="row-between wrap">
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{unified.summary || "当前暂无一句话结论"}</div>
              {unified.narrative && <div className="secondary mt-6" style={{ fontSize: 13 }}>{unified.narrative}</div>}
            </div>
            <div style={{ minWidth: 200 }}>
              {unified.confidence != null && <ConfidenceBar value={unified.confidence} />}
            </div>
          </div>
          <div className="grid grid-2 mt-14">
            {unified.longSummary && (
              <div>
                <div className="bull-text strong" style={{ fontSize: 12 }}>多头情景</div>
                <div className="secondary" style={{ fontSize: 12, marginTop: 3 }}>{unified.longSummary}</div>
              </div>
            )}
            {unified.shortSummary && (
              <div>
                <div className="bear-text strong" style={{ fontSize: 12 }}>空头情景</div>
                <div className="secondary" style={{ fontSize: 12, marginTop: 3 }}>{unified.shortSummary}</div>
              </div>
            )}
          </div>
          {unified.holdingSummary && (
            <div className="mt-14">
              <div className="accent-text strong" style={{ fontSize: 12 }}>持仓观察</div>
              <div className="secondary" style={{ fontSize: 12, marginTop: 3 }}>{unified.holdingSummary}</div>
            </div>
          )}
          {unified.riskNotes && unified.riskNotes.length > 0 && (
            <div className="mt-10">
              {unified.riskNotes.slice(0, 4).map((r, i) => (
                <div key={i} className="muted" style={{ fontSize: 12 }}>· {r}</div>
              ))}
            </div>
          )}
          <div className="muted mt-10" style={{ fontSize: 11 }}>
            行情数据时间 {unified.dataTimestamp || "—"} · 分析生成 {unified.generated_at}
          </div>
        </Card>
      )}

      {/* Risk map */}
      {riskMap && riskMap.timeframes && Object.keys(riskMap.timeframes).length > 0 && (
        <Card title="风险地图" sub="多周期结构风险" right={<Badge tone={riskMap.overall_risk === "high" ? "bear" : riskMap.overall_risk === "medium" ? "warn" : "neutral"}>{riskMap.overall_risk ?? "—"}</Badge>}>
          <div className="data-table" style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th className="th-num" style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)" }}>周期</th>
                  <th className="th-num" style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)" }}>趋势</th>
                  <th className="th-num" style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)" }}>支撑</th>
                  <th className="th-num" style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)" }}>阻力</th>
                  <th className="th-num" style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)" }}>风险</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(riskMap.timeframes ?? {}).map(([tf, row]) => (
                  <tr key={tf}>
                    <td className="num strong">{tf}</td>
                    <td className="num">{row.trend ?? "—"}</td>
                    <td className="num bull-text">{fmtPrice(row.support)}</td>
                    <td className="num bear-text">{fmtPrice(row.resistance)}</td>
                    <td className="num">
                      <Badge tone={row.risk === "high" ? "bear" : row.risk === "medium" ? "warn" : "neutral"}>{row.risk ?? "—"}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {riskMap.summary && <div className="muted mt-10" style={{ fontSize: 12 }}>{riskMap.summary}</div>}
        </Card>
      )}

      {/* Feedback chain */}
      {feedback && (
        <Card
          title="历史分析反馈"
          sub="原始报告冻结 · 后续行情只生成反馈"
          right={
            <Badge tone={feedback.currentState === "validated" ? "bull" : feedback.currentState === "invalidated" ? "bear" : feedback.currentState === "tracking" ? "accent" : "neutral"}>
              {feedback.currentState === "validated" ? "阶段验证" : feedback.currentState === "invalidated" ? "已失效" : feedback.currentState === "tracking" ? "继续跟踪" : "等待反馈"}
            </Badge>
          }
        >
          {feedback.currentSummary && <div className="secondary" style={{ fontSize: 13 }}>{feedback.currentSummary}</div>}
          <div className="mt-10">
            {(feedback.history ?? []).slice(0, 6).map((h, i) => (
              <div key={i} className="feed-item" style={{ borderBottom: "1px solid var(--border-soft)" }}>
                <div className="grow">
                  <div className="row">
                    <span className="mono strong" style={{ fontSize: 12 }}>{h.reportId || `反馈 ${i + 1}`}</span>
                    <span className="muted" style={{ fontSize: 11 }}>{directionLabel(h.direction)} · {(h.confidence ?? 0) * 100}%</span>
                  </div>
                  {h.feedbackSummary && <div className="summary">{h.feedbackSummary}</div>}
                </div>
                <Badge tone={h.feedbackState === "validated" ? "bull" : h.feedbackState === "invalidated" ? "bear" : h.feedbackState === "tracking" ? "accent" : "neutral"}>
                  {h.feedbackState === "validated" ? "验证" : h.feedbackState === "invalidated" ? "失效" : h.feedbackState === "tracking" ? "跟踪" : "等待"}
                </Badge>
              </div>
            ))}
            {(feedback.history ?? []).length === 0 && <div className="empty">尚无反馈记录；报告生成后将在后续行情中自动跟踪验证。</div>}
          </div>
          <div className="muted mt-10" style={{ fontSize: 11 }}>
            历史报告为冻结快照，周期切换后重新生成独立分析与反馈链。
          </div>
        </Card>
      )}

      {/* Derivatives (crypto) */}
      {derivatives && (
        <Card
          title="合约市场结构"
          sub="公开市场数据 · 只读"
          right={<Badge tone={derivatives.available ? "bull" : "warn"}>{derivatives.available ? "PUBLIC DATA" : "数据源不可用"}</Badge>}
        >
          {derivatives.available ? (
            <div className="kv">
              <div className="item">
                <div className="k">标记价格</div>
                <div className="v">{fmtPrice(derivatives.mark_index?.mark_price)}</div>
              </div>
              <div className="item">
                <div className="k">指数价格</div>
                <div className="v">{fmtPrice(derivatives.mark_index?.index_price)}</div>
              </div>
              <div className="item">
                <div className="k">资金费率</div>
                <div className="v">{derivatives.mark_index?.last_funding_rate != null ? (derivatives.mark_index.last_funding_rate * 100).toFixed(4) + "%" : "—"}</div>
              </div>
              <div className="item">
                <div className="k">未平仓量</div>
                <div className="v">{derivatives.open_interest?.latest?.open_interest != null ? fmtNum(derivatives.open_interest.latest.open_interest) : "—"}</div>
              </div>
            </div>
          ) : (
            <div className="empty">
              合约衍生品数据源（资金费率 / 持仓量 / 多空比）当前不可达；现货行情与分析不受影响。以上均为公开市场数据，只用于判断拥挤度与价格结构，不代表交易执行。
            </div>
          )}
        </Card>
      )}

      {/* Multi-exchange */}
      {multiExchange && (
        <Card
          title="多交易所一致性"
          sub="现货价格共识 · 只读"
          right={<Badge tone={multiExchange.available_provider_count > 0 ? "bull" : "warn"}>{multiExchange.available_provider_count}/3 可用</Badge>}
        >
          {multiExchange.providers.map((p) => (
            <div key={p.provider} className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong">{p.provider.toUpperCase()}</span>
              <span className="secondary mono">
                {p.available ? `${fmtPrice(p.mark_price)} · 资金费率 ${p.funding_rate != null ? (p.funding_rate * 100).toFixed(4) + "%" : "—"}` : "不可用"}
              </span>
            </div>
          ))}
          {multiExchange.consensus?.mark_price_mean != null && (
            <div className="muted mt-10" style={{ fontSize: 12 }}>
              共识价格 {fmtPrice(multiExchange.consensus.mark_price_mean)} · 价格离散{" "}
              {multiExchange.divergence?.mark_price_spread_pct != null ? multiExchange.divergence.mark_price_spread_pct.toFixed(4) + "%" : "—"}
            </div>
          )}
        </Card>
      )}

      {/* Data capability */}
      {snapshot && (
        <Card title={`数据能力 · ${snapshot.market?.toUpperCase?.() ?? "CRYPTO"}`}>
          <div className="row wrap">
            <Badge tone={snapshot.snapshotAvailable ? "bull" : "bear"}>{snapshot.snapshotAvailable ? "行情可用" : "行情不可用"}</Badge>
            <Badge tone={snapshot.capabilityStatus === "available" ? "bull" : "warn"}>{snapshot.capabilityStatus ?? "—"}</Badge>
          </div>
          <div className="muted mt-10" style={{ fontSize: 12 }}>
            Provider {snapshot.provider} · {snapshot.timeframe} · 数据质量 {snapshot.quality} · {snapshot.realtime ? "实时" : "非实时"}
            {snapshot.missing?.length ? ` · 缺失能力：${snapshot.missing.join("、")}` : ""}
          </div>
        </Card>
      )}

      {/* Indicators summary narrative */}
      {indicators?.narrative && (
        <Card title="指标解读">
          <div className="secondary" style={{ fontSize: 13 }}>{indicators.narrative}</div>
        </Card>
      )}

      {/* P26 intelligent enhancements */}
      {(p26Regime || p26Quality || p26Attribution || p26Calibration || p26Memory) && (
        <Card
          title="智能增强 · P26"
          sub="状态路由 / 数据质量 / 反馈归因 / 置信度校准 / 相似情景"
        >
          {p26Regime && (
            <div className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong">市场状态路由</span>
              <span>
                <Badge tone={p26Regime.trend === "up" ? "bull" : p26Regime.trend === "down" ? "bear" : "neutral"}>{p26Regime.regime}</Badge>
                <span className="muted mono" style={{ marginLeft: 8, fontSize: 12 }}>{p26Regime.detail}</span>
              </span>
            </div>
          )}
          {p26Quality && (
            <div className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong">数据质量评分卡</span>
              <span>
                <Badge tone={p26Quality.score >= 90 ? "bull" : p26Quality.score >= 75 ? "warn" : "bear"}>{p26Quality.grade} · {p26Quality.score}/100</Badge>
                <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                  {p26Quality.checks.filter((c) => c.ok).length}/{p26Quality.checks.length} 项通过
                </span>
              </span>
            </div>
          )}
          {p26Attribution && (
            <div style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <div className="row-between">
                <span className="strong">反馈归因 · 多情景并行跟踪</span>
                <span className="secondary" style={{ fontSize: 12 }}>
                  {p26Attribution.total_count} 条历史反馈 · 已决 {p26Attribution.resolved_count} 条
                  {p26Attribution.accuracy_pct != null ? ` · 验证率 ${p26Attribution.accuracy_pct.toFixed(1)}%` : ""}
                </span>
              </div>
              {!!p26Attribution.direction_stats?.length && (
                <div className="row wrap mt-6" style={{ gap: 8 }}>
                  {p26Attribution.direction_stats!.map((d) => (
                    <div key={d.direction} className="stat-card" style={{ padding: "6px 10px", minWidth: 130 }}>
                      <div className="muted" style={{ fontSize: 11 }}>
                        {d.direction === "long" ? "多头" : d.direction === "short" ? "空头" : "中性"} · {d.total} 条
                      </div>
                      <div style={{ fontSize: 12, marginTop: 2 }}>
                        验证 {d.validated} · 失效 {d.invalidated} · 跟踪 {d.tracking}
                        {d.accuracy_pct != null ? ` · ${d.accuracy_pct}%` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {p26Calibration && (
            <div className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong">置信度校准</span>
              <span className="secondary" style={{ fontSize: 12 }}>
                {p26Calibration.sample_count > 0
                  ? `已校准 · Brier ${p26Calibration.brier_score}（${p26Calibration.sample_count} 样本）`
                  : "未校准 · 等待已验证样本积累"}
              </span>
            </div>
          )}
          {p26Memory && (
            <div className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong">相似情景记忆</span>
              <span className="secondary" style={{ fontSize: 12 }}>
                {p26Memory.situation_count} 类历史结构
                {p26Memory.similar_situation
                  ? ` · 当前结构历史 ${p26Memory.similar_situation.count} 次（验证 ${p26Memory.similar_situation.validated} / 失效 ${p26Memory.similar_situation.invalidated}）`
                  : " · 当前结构暂无历史样本"}
              </span>
            </div>
          )}
          {(p26Quality || p26Attribution || p26Calibration || p26Memory) && (
            <div className="muted mt-10" style={{ fontSize: 12 }}>
              {[p26Quality?.quality_note, p26Attribution?.sample_note, p26Calibration?.note, p26Memory?.note]
                .filter(Boolean)
                .map((n, i) => <div key={i}>· {n}</div>)}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
