export function fmtPrice(v?: number | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (Math.abs(v) >= 1) return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return v.toLocaleString("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 6 });
}

export function fmtPct(v?: number | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}%`;
}

export function fmtNum(v?: number | null, digits = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtCompact(v?: number | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(0);
}

export function fmtTime(ms?: number | string | null): string {
  if (!ms) return "—";
  const n = typeof ms === "string" ? Number(ms) : ms;
  const d = new Date(n);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function fmtDateTime(ms?: number | string | null): string {
  if (!ms) return "—";
  const n = typeof ms === "string" ? Number(ms) : ms;
  const d = new Date(n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function directionLabel(d?: string): string {
  switch (d) {
    case "long": return "多头";
    case "short": return "空头";
    case "neutral": return "中性";
    default: return "观察";
  }
}

export function directionColor(d?: string): "bull" | "bear" | "neutral" | "accent" {
  switch (d) {
    case "long": return "bull";
    case "short": return "bear";
    case "neutral": return "neutral";
    default: return "accent";
  }
}

export function marketLabel(m?: string): string {
  switch (m) {
    case "crypto": return "加密";
    case "us": return "美股";
    case "hk": return "港股";
    case "commodities": return "大宗";
    default: return m ?? "—";
  }
}

export const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

export const MARKET_TABS: { key: string; label: string }[] = [
  { key: "crypto", label: "加密" },
  { key: "us", label: "美股" },
  { key: "hk", label: "港股" },
  { key: "commodities", label: "大宗" },
];

export const REPORT_DOMAINS = ["全部", "行情", "技术", "资金", "基本面", "事件", "风险", "研究", "复盘"];
