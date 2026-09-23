import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../App";
import { Card, Badge } from "../components";
import { fmtPrice, fmtPct, fmtTime } from "../format";
import { api } from "../api";

interface AutoAlert {
  symbol: string;
  name: string;
  venue: string;
  level: "P0" | "P1" | "P2";
  kind: string;
  messages: string[];
  change_pct: number;
  price?: number | null;
  quote_volume?: number | null;
}
interface UserAlert {
  id: number;
  symbol: string;
  kind: string;
  operator: string;
  threshold: number;
  enabled: boolean;
}
interface AlertsCenter {
  auto_alerts: AutoAlert[];
  user_alerts: UserAlert[];
  level_counts: Record<string, number>;
  merge_note: string;
  generated_at: number;
}

const DND_KEY = "smart-trader-dnd";
const toneFor = (l: string) => (l === "P0" ? "bear" : l === "P1" ? "warn" : "neutral");

export default function Alerts() {
  const navigate = useNavigate();
  const { backendOnline } = useApp();
  const [data, setData] = useState<AlertsCenter | null>(null);
  const [loading, setLoading] = useState(true);
  const [dnd, setDnd] = useState<{ start: string; end: string; on: boolean }>(() => {
    try {
      return JSON.parse(localStorage.getItem(DND_KEY) || "") || { start: "22:00", end: "08:00", on: false };
    } catch {
      return { start: "22:00", end: "08:00", on: false };
    }
  });

  const load = () => {
    api.p26AlertsCenter({ limit: 40 }).then((d) => setData(d)).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const saveDnd = (next: typeof dnd) => {
    setDnd(next);
    localStorage.setItem(DND_KEY, JSON.stringify(next));
  };

  const levelOrder: ("P0" | "P1" | "P2")[] = ["P0", "P1", "P2"];

  return (
    <div>
      <div className="row-between mb-14 wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>预警中心</h1>
          <div className="muted">分级预警 · 合并推送 · 免打扰设置 · 只读</div>
        </div>
        {backendOnline ? <Badge tone="bull">ONLINE</Badge> : <Badge tone="bear">OFFLINE</Badge>}
      </div>

      <div className="row wrap mb-14" style={{ gap: 10 }}>
        {levelOrder.map((l) => (
          <div key={l} className="stat-card" style={{ minWidth: 120 }}>
            <div className="muted" style={{ fontSize: 12 }}>{l} 级异动</div>
            <div className="strong" style={{ fontSize: 22 }}>{data?.level_counts[l] ?? "—"}</div>
          </div>
        ))}
      </div>

      <Card
        title="自动分级预警"
        sub="基于实时行情涨跌幅异动 · 同一标的多条异动已合并"
        right={<Badge tone="neutral">{data ? `${data.auto_alerts.length} 条` : "加载中"}</Badge>}
      >
        {loading && <div className="empty">加载预警中…</div>}
        {!loading && (!data || data.auto_alerts.length === 0) && (
          <div className="empty">当前无显著异动（阈值：P2 ≥4% / P1 ≥8% / P0 ≥15%）</div>
        )}
        {data?.auto_alerts.map((a) => (
          <div
            key={a.symbol}
            className="row-between"
            style={{ padding: "9px 0", borderBottom: "1px solid var(--border-soft)", cursor: "pointer" }}
            onClick={() => navigate(`/symbol/${a.symbol}`)}
          >
            <div>
              <div className="row" style={{ gap: 8 }}>
                <Badge tone={toneFor(a.level)}>{a.level}</Badge>
                <span className="strong">{a.symbol}</span>
                <span className="muted" style={{ fontSize: 11 }}>{a.venue}</span>
              </div>
              <div className="muted mt-4" style={{ fontSize: 12 }}>
                {a.messages.join(" · ")} · 最新 {a.price != null ? fmtPrice(a.price) : "—"}
              </div>
            </div>
            <span className="mono strong" style={{ color: a.change_pct >= 0 ? "var(--bull)" : "var(--bear)" }}>
              {fmtPct(a.change_pct)}
            </span>
          </div>
        ))}
        <div className="muted mt-10" style={{ fontSize: 12 }}>{data?.merge_note}</div>
      </Card>

      <Card title="我的预警" sub="自定义价格/指标条件提醒（仅本地分析，不推送外部）">
        {data?.user_alerts.length ? (
          data.user_alerts.map((u) => (
            <div key={u.id} className="row-between" style={{ padding: "7px 0", borderBottom: "1px solid var(--border-soft)" }}>
              <span className="strong" style={{ fontSize: 13 }}>{u.symbol}</span>
              <span className="secondary" style={{ fontSize: 12 }}>
                {u.kind} {u.operator} {u.threshold} · {u.enabled ? "启用" : "停用"}
              </span>
            </div>
          ))
        ) : (
          <div className="empty">暂无自定义预警（API：POST /api/v1/alerts 创建）</div>
        )}
      </Card>

      <Card title="免打扰设置" sub="静默时段内不打扰（本地保存）">
        <div className="row wrap" style={{ gap: 12, alignItems: "center" }}>
          <label style={{ fontSize: 13 }}>开始</label>
          <input
            type="time"
            value={dnd.start}
            onChange={(e) => saveDnd({ ...dnd, start: e.target.value })}
            style={{ background: "var(--bg-soft)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 8px" }}
          />
          <label style={{ fontSize: 13 }}>结束</label>
          <input
            type="time"
            value={dnd.end}
            onChange={(e) => saveDnd({ ...dnd, end: e.target.value })}
            style={{ background: "var(--bg-soft)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 8px" }}
          />
          <button
            onClick={() => saveDnd({ ...dnd, on: !dnd.on })}
            style={{
              background: dnd.on ? "var(--bull)" : "var(--bg-soft)",
              color: dnd.on ? "#06120d" : "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 6, padding: "6px 14px", cursor: "pointer", fontWeight: 600,
            }}
          >
            {dnd.on ? "已开启免打扰" : "开启免打扰"}
          </button>
          {dnd.on && <span className="muted" style={{ fontSize: 12 }}>{dnd.start} – {dnd.end} 静默</span>}
        </div>
      </Card>

      <div className="muted mt-10" style={{ fontSize: 12 }}>
        预警仅作行情观察提示，不构成投资建议。市场有风险，决策需谨慎。
      </div>
    </div>
  );
}
