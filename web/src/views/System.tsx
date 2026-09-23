import React, { useEffect, useState } from "react";
import { useApp } from "../App";
import { Card, Badge, ProviderHealthBar } from "../components";
import { marketLabel, fmtDateTime, fmtTime } from "../format";
import { api } from "../api";
import type { MarketCoverageItem, P26Audit } from "../types";

function coverageCount(v: number | MarketCoverageItem | undefined): number {
  if (typeof v === "number") return v;
  return v?.count ?? 0;
}

export default function System() {
  const { backendOnline, runtime, providerHealth, capabilities, coverage, markets, refreshTick } = useApp();
  const [audit, setAudit] = useState<P26Audit | null>(null);
  const coverageTotal: number =
    coverage?.total ??
    Object.values(coverage?.markets ?? {}).reduce<number>((acc, v) => acc + coverageCount(v), 0);

  useEffect(() => {
    let alive = true;
    api.p26Audit({ limit: 30 }).then((d) => alive && setAudit(d)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [refreshTick]);

  return (
    <div>
      <div className="row-between mb-14 wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>数据与系统</h1>
          <div className="muted">Smart Trader Web 运行状态与数据能力</div>
        </div>
        {backendOnline ? <Badge tone="bull">ONLINE</Badge> : <Badge tone="bear">OFFLINE</Badge>}
      </div>

      <Card title="连接状态">
        <div className="row-between wrap">
          <div>
            <div className="strong">{backendOnline ? "后端已连接" : "后端不可达"}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              API 地址：/api/v1（同源服务） · 数据刷新：REST 轮询 + 行情缓存
            </div>
          </div>
          <Badge tone={backendOnline ? "bull" : "bear"}>{backendOnline ? "在线" : "离线"}</Badge>
        </div>
      </Card>

      {runtime && (
        <Card title="Backend 运行实例">
          <div className="kv">
            <div className="item">
              <div className="k">API 版本</div>
              <div className="v">v{runtime.version}</div>
            </div>
            <div className="item">
              <div className="k">行情网关</div>
              <div className="v" style={{ fontSize: 13 }}>{runtime.crypto_gateway.providers.join(" → ")}</div>
            </div>
            <div className="item">
              <div className="k">行情接口</div>
              <div className="v" style={{ fontSize: 13 }}>{runtime.crypto_gateway.market_endpoint}</div>
            </div>
            <div className="item">
              <div className="k">服务器时间</div>
              <div className="v" style={{ fontSize: 13 }}>{fmtDateTime(runtime.server_time_ms)}</div>
            </div>
          </div>
        </Card>
      )}

      <Card title="Provider 健康" sub="真实 provider 状态，不可用不会伪装">
        <ProviderHealthBar providers={providerHealth} order={runtime?.crypto_gateway.providers} />
        <div className="mt-10">
          {providerHealth.map((p) => (
            <div key={p.name} className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <div>
                <span className="strong">{p.name.toUpperCase()}</span>
                {p.message && <span className="muted" style={{ fontSize: 11, marginLeft: 8 }}>{p.message}</span>}
              </div>
              <Badge tone={p.available ? "bull" : "bear"}>{p.available ? "可用" : "不可用"}</Badge>
            </div>
          ))}
        </div>
      </Card>

      <Card title="四大市场数据能力" sub="能力矩阵 · 真实来源">
        {capabilities?.markets ? (
          <div className="data-table" style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "left" }}>市场</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "left" }}>Provider</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "center" }}>行情</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "center" }}>K线</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "center" }}>实时</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "center" }}>衍生品</th>
                  <th style={{ padding: "8px 10px", color: "var(--text-muted)", fontSize: 11, borderBottom: "1px solid var(--border)", textAlign: "left" }}>缺失</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(capabilities.markets).map(([key, c]) => (
                  <tr key={key}>
                    <td className="strong" style={{ padding: "8px 10px" }}>{marketLabel(key)}</td>
                    <td className="muted" style={{ padding: "8px 10px", fontSize: 11 }}>{c.provider}</td>
                    <td style={{ padding: "8px 10px", textAlign: "center" }}>{c.quote ? <Badge tone="bull">✓</Badge> : <Badge tone="bear">✗</Badge>}</td>
                    <td style={{ padding: "8px 10px", textAlign: "center" }}>{c.candles ? <Badge tone="bull">✓</Badge> : <Badge tone="bear">✗</Badge>}</td>
                    <td style={{ padding: "8px 10px", textAlign: "center" }}>{c.realtime ? <Badge tone="bull">✓</Badge> : <Badge tone="warn">—</Badge>}</td>
                    <td style={{ padding: "8px 10px", textAlign: "center" }}>{c.derivatives ? <Badge tone="bull">✓</Badge> : <Badge tone="warn">—</Badge>}</td>
                    <td className="warn-text" style={{ padding: "8px 10px", fontSize: 11 }}>{(c.missing || []).join("、")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">等待后端返回能力矩阵…</div>
        )}
      </Card>

      <Card title="全量市场覆盖" sub="品种发现统计">
        {coverage ? (
          <div className="row wrap">
            {Object.entries(coverage.markets || {}).map(([m, v]) => {
              const count = coverageCount(v);
              const note = typeof v === "object" && v ? (v.universe ? ` · ${v.universe}` : "") : "";
              return (
                <span key={m} className="pill">
                  {marketLabel(m)} = {count}
                  {note && <span className="muted" style={{ fontSize: 10, marginLeft: 4 }}>{note}</span>}
                </span>
              );
            })}
            <span className="pill">总计 {coverageTotal}</span>
          </div>
        ) : (
          <div className="empty">等待覆盖统计…</div>
        )}
      </Card>

      <Card title="产品边界">
        <div className="secondary" style={{ fontSize: 13 }}>
          只读分析平台：行情、K线、指标、市场结构、多空情景、持仓观察、历史报告反馈、32 类研究报告。
        </div>
        <div className="muted mt-6" style={{ fontSize: 12 }}>
          不包含模拟盘、纸面成交、真实下单或交易账户连接；不代管资金、不签名交易、不触碰提现权限。
        </div>
        <div className="muted mt-6" style={{ fontSize: 12 }}>
          任何未配置的数据源必须显示为不可用/等待 provider，不使用零值或默认值伪装成真实行情。
        </div>
      </Card>

      <Card title="报告审计链 · P26" sub="历史报告 SHA-256 冻结，只读不可篡改">
        {audit ? (
          audit.items.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ color: "var(--text-muted)" }}>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>报告 ID</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>标的 / 周期</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>方向</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>版本</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>SHA-256</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-soft)" }}>冻结时间</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.items.map((a) => (
                    <tr key={a.report_id}>
                      <td style={{ padding: "6px 8px", fontFamily: "var(--font-mono)" }}>{a.report_id}</td>
                      <td style={{ padding: "6px 8px" }}>{a.symbol} · {a.timeframe}</td>
                      <td style={{ padding: "6px 8px" }}>{a.direction}</td>
                      <td style={{ padding: "6px 8px" }}>v{a.version}</td>
                      <td style={{ padding: "6px 8px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{a.sha256.slice(0, 16)}…</td>
                      <td style={{ padding: "6px 8px", color: "var(--text-muted)" }}>{fmtTime(a.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">暂无冻结报告（每次生成分析快照时自动写入审计链）</div>
          )
        ) : (
          <div className="empty">加载审计链…</div>
        )}
        <div className="muted mt-10" style={{ fontSize: 12 }}>
          {audit ? `共 ${audit.count} 条冻结记录 · 不可变存储（append-only）` : "审计链按需加载"}
        </div>
      </Card>

      <Card title="本地刷新">
        <div className="muted" style={{ fontSize: 12 }}>
          页面每 15 秒自动刷新一次行情与分析（当前 tick {refreshTick}）。切换周期、搜索与排序均在本地即时完成，真实数据来自后端网关。
        </div>
      </Card>
    </div>
  );
}
