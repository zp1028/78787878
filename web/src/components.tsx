import React from "react";
import { fmtPrice, fmtPct, fmtCompact, fmtTime, directionLabel, directionColor } from "./format";
import type { MarketRow, ProviderHealth } from "./types";

export function Badge({ tone, children }: { tone: "bull" | "bear" | "accent" | "warn" | "neutral"; children: React.ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Card({ title, sub, right, children, className = "" }: { title?: string; sub?: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={`card ${className}`}>
      {(title || right) && (
        <div className="card-title">
          <div>
            {title && <h2>{title}</h2>}
            {sub && <div className="sub">{sub}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function StatCard({ label, value, note, tone }: { label: string; value: React.ReactNode; note?: string; tone?: "bull" | "bear" | "accent" }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className={`value ${tone ? `${tone}-text` : ""}`}>{value}</div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}

export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button className={`chip ${active ? "active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

export function PctCell({ value }: { value?: number | null }) {
  const tone = value == null ? "neutral" : value > 0 ? "bull" : value < 0 ? "bear" : "neutral";
  return <span className={`num ${tone}-text strong`}>{fmtPct(value)}</span>;
}

export function MarketRowItem({ m, onOpen }: { m: MarketRow; onOpen: () => void }) {
  return (
    <div className="market-row" onClick={onOpen}>
      <div style={{ flex: 1.2, minWidth: 110 }}>
        <div className="sym">{m.symbol}</div>
        <div className="muted" style={{ fontSize: 11 }}>
          {m.name} · {m.venue || m.market?.toUpperCase()}
        </div>
      </div>
      <div style={{ flex: 0.8, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        <div className="strong">{fmtPrice(m.price)}</div>
        <div className="muted" style={{ fontSize: 11 }}>{m.currency || "市场价"}</div>
      </div>
      <div style={{ flex: 0.7, textAlign: "right" }}>
        <PctCell value={m.change_pct} />
      </div>
      <div style={{ flex: 0.9, textAlign: "right", display: "none", fontSize: 12 }} className="secondary">
        {fmtCompact(m.quote_volume)}
      </div>
      <div style={{ flex: 0.5, textAlign: "right" }}>
        {m.quote_status === "live" ? <Badge tone="bull">实时</Badge> : <Badge tone="warn">{m.quote_status || "等待"}</Badge>}
      </div>
    </div>
  );
}

export function ProviderHealthBar({ providers, order }: { providers: ProviderHealth[]; order?: string[] }) {
  const ordered = order?.length ? [...providers].sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name)) : providers;
  return (
    <div className="row wrap">
      {ordered.map((p) => (
        <span key={p.name} className="pill">
          {p.name.toUpperCase()} = {p.available ? <span className="bull-text">UP</span> : <span className="bear-text">DOWN</span>}
        </span>
      ))}
    </div>
  );
}

export function DirectionBadge({ direction }: { direction?: string }) {
  return <Badge tone={directionColor(direction)}>{directionLabel(direction)}</Badge>;
}

export function ConfidenceBar({ value }: { value?: number }) {
  if (value == null) return null;
  const pct = Math.max(0, Math.min(100, value * 100));
  const color = pct >= 75 ? "#26a69a" : pct >= 55 ? "#4fc3f7" : "#8a94a6";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "#1a2230", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span className="mono strong" style={{ fontSize: 12, color }}>{pct.toFixed(0)}%</span>
    </div>
  );
}
