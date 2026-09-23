import * as echarts from "echarts";
import type { Candle, IndicatorReport, Scenario } from "./types";

export const CHART_BG = "transparent";
export const COLOR_UP = "#26a69a";
export const COLOR_DOWN = "#ef5350";
export const COLOR_ACCENT = "#4fc3f7";
export const COLOR_TEXT = "#aab4c4";
export const COLOR_MUTED = "#6b7688";
export const COLOR_GRID = "#1c2535";

function baseGrid(extra?: object) {
  return { left: 52, right: 16, top: 14, bottom: 22, ...extra };
}

// Candlestick + MA overlay + volume
export function renderCandleChart(el: HTMLElement, candles: Candle[], indicators?: IndicatorReport) {
  const chart = echarts.init(el);
  const dates = candles.map((c) => {
    const d = new Date(c.open_time);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  const ohlc = candles.map((c) => [c.open, c.close, c.low, c.high]);
  const vols = candles.map((c, i) => ({
    value: c.volume,
    itemStyle: { color: c.close >= c.open ? COLOR_UP : COLOR_DOWN, opacity: 0.65 },
  }));

  const closes = candles.map((c) => c.close);
  const ma = (period: number) =>
    closes.map((_, i) => {
      if (i < period - 1) return null;
      const slice = closes.slice(i - period + 1, i + 1);
      return Number((slice.reduce((a, b) => a + b, 0) / period).toFixed(2));
    });

  const series: echarts.SeriesOption[] = [
    {
      name: "K线",
      type: "candlestick",
      data: ohlc,
      itemStyle: { color: COLOR_UP, color0: COLOR_DOWN, borderColor: COLOR_UP, borderColor0: COLOR_DOWN },
      xAxisIndex: 0,
      yAxisIndex: 0,
    },
    { name: "MA20", type: "line", data: ma(20), symbol: "none", lineStyle: { width: 1, color: "#f5a623" }, xAxisIndex: 0, yAxisIndex: 0 },
    { name: "MA50", type: "line", data: ma(50), symbol: "none", lineStyle: { width: 1, color: "#4fc3f7" }, xAxisIndex: 0, yAxisIndex: 0 },
    { name: "成交量", type: "bar", data: vols, xAxisIndex: 1, yAxisIndex: 1, barWidth: "62%" },
  ];

  // Bollinger bands from indicator report if available
  if (indicators?.bb_upper && indicators.bb_lower) {
    series.push(
      { name: "BB上轨", type: "line", data: candles.map(() => indicators.bb_upper), symbol: "none", lineStyle: { width: 1, type: "dashed", color: "rgba(138,148,166,0.55)" }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: "BB下轨", type: "line", data: candles.map(() => indicators.bb_lower), symbol: "none", lineStyle: { width: 1, type: "dashed", color: "rgba(138,148,166,0.55)" }, xAxisIndex: 0, yAxisIndex: 0 },
    );
  }

  chart.setOption({
    backgroundColor: CHART_BG,
    animation: false,
    axisPointer: { link: [{ xAxisIndex: "all" }], label: { backgroundColor: "#232e40" } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "#141a26",
      borderColor: "#232e40",
      textStyle: { color: "#e6e9ef", fontSize: 12 },
    },
    legend: { show: false },
    grid: [
      baseGrid({ bottom: 118 }),
      { left: 52, right: 16, top: "70%", height: "22%" },
    ],
    xAxis: [
      { type: "category", gridIndex: 0, data: dates, boundaryGap: true, axisLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { color: COLOR_MUTED, fontSize: 10 }, splitLine: { show: false } },
      { type: "category", gridIndex: 1, data: dates, axisLabel: { show: false }, axisLine: { lineStyle: { color: COLOR_GRID } } },
    ],
    yAxis: [
      { type: "value", gridIndex: 0, scale: true, splitLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { color: COLOR_MUTED, fontSize: 10 } },
      { type: "value", gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series,
  });
  return chart;
}

// RSI sub-chart
export function renderRsiChart(el: HTMLElement, candles: Candle[], period = 14) {
  const chart = echarts.init(el);
  const rsi = calcRsi(candles.map((c) => c.close), period);
  const dates = candles.map((c) => {
    const d = new Date(c.open_time);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  chart.setOption({
    backgroundColor: CHART_BG,
    animation: false,
    tooltip: { trigger: "axis", backgroundColor: "#141a26", borderColor: "#232e40", textStyle: { color: "#e6e9ef", fontSize: 12 } },
    grid: baseGrid(),
    xAxis: { type: "category", data: dates, axisLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { show: false } },
    yAxis: { min: 0, max: 100, splitLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { color: COLOR_MUTED, fontSize: 10 } },
    series: [
      {
        name: `RSI(${period})`,
        type: "line",
        data: rsi,
        symbol: "none",
        lineStyle: { width: 1.2, color: COLOR_ACCENT },
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            { yAxis: 70, lineStyle: { color: "rgba(239,83,80,0.4)", type: "dashed" }, label: { show: false } },
            { yAxis: 30, lineStyle: { color: "rgba(38,166,154,0.4)", type: "dashed" }, label: { show: false } },
          ],
        },
      },
    ],
  });
  return chart;
}

// MACD sub-chart
export function renderMacdChart(el: HTMLElement, candles: Candle[]) {
  const chart = echarts.init(el);
  const closes = candles.map((c) => c.close);
  const ema12 = calcEma(closes, 12);
  const ema26 = calcEma(closes, 26);
  const dif = ema12.map((v, i) => (v != null && ema26[i] != null ? v - ema26[i]! : null));
  const dea = calcEma(dif.map((v) => v ?? 0), 9);
  const hist = dif.map((v, i) => (v != null && dea[i] != null ? v - dea[i] : null));
  const dates = candles.map((c) => {
    const d = new Date(c.open_time);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  chart.setOption({
    backgroundColor: CHART_BG,
    animation: false,
    tooltip: { trigger: "axis", backgroundColor: "#141a26", borderColor: "#232e40", textStyle: { color: "#e6e9ef", fontSize: 12 } },
    grid: baseGrid(),
    xAxis: { type: "category", data: dates, axisLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { show: false } },
    yAxis: { scale: true, splitLine: { lineStyle: { color: COLOR_GRID } }, axisLabel: { color: COLOR_MUTED, fontSize: 10 } },
    series: [
      { name: "DIF", type: "line", data: dif, symbol: "none", lineStyle: { width: 1, color: "#f5a623" } },
      { name: "DEA", type: "line", data: dea, symbol: "none", lineStyle: { width: 1, color: COLOR_ACCENT } },
      {
        name: "MACD",
        type: "bar",
        data: hist.map((v) => ({ value: v, itemStyle: { color: (v ?? 0) >= 0 ? COLOR_UP : COLOR_DOWN, opacity: 0.7 } })),
        barWidth: "55%",
      },
    ],
  });
  return chart;
}

// Donut chart for scenario probability / confidence
export function renderDonut(el: HTMLElement, data: { name: string; value: number; color: string }[], centerText: string) {
  const chart = echarts.init(el);
  chart.setOption({
    backgroundColor: CHART_BG,
    tooltip: { trigger: "item", backgroundColor: "#141a26", borderColor: "#232e40", textStyle: { color: "#e6e9ef" }, formatter: "{b}: {c}%" },
    series: [
      {
        type: "pie",
        radius: ["58%", "82%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: { scale: false },
        data: data.map((d) => ({ name: d.name, value: d.value, itemStyle: { color: d.color } })),
      },
    ],
    graphic: [
      {
        type: "text",
        left: "center",
        top: "42%",
        style: { text: centerText, textAlign: "center", fill: "#e6e9ef", fontSize: 18, fontWeight: 700 },
      },
    ],
  });
  return chart;
}

// Multi-timeframe risk table heat cells are rendered in React; this is a simple bar
export function renderMiniBars(el: HTMLElement, items: { label: string; value: number }[]) {
  const chart = echarts.init(el);
  chart.setOption({
    backgroundColor: CHART_BG,
    grid: { left: 8, right: 8, top: 8, bottom: 8 },
    xAxis: { type: "value", show: false },
    yAxis: { type: "category", data: items.map((i) => i.label), show: false },
    series: [
      {
        type: "bar",
        data: items.map((i) => ({ value: i.value, itemStyle: { color: i.value >= 0 ? COLOR_UP : COLOR_DOWN, borderRadius: 3 } })),
        barWidth: 10,
      },
    ],
  });
  return chart;
}

function calcRsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < closes.length; i++) {
    if (i === 0) {
      out.push(null);
      continue;
    }
    const change = closes[i] - closes[i - 1];
    const gain = Math.max(change, 0);
    const loss = Math.max(-change, 0);
    if (i <= period) {
      avgGain += gain;
      avgLoss += loss;
      if (i === period) {
        avgGain /= period;
        avgLoss /= period;
        out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
      } else {
        out.push(null);
      }
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
    }
  }
  return out;
}

function calcEma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (period + 1);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (prev == null) {
      prev = values[i];
      out.push(prev);
    } else {
      prev = values[i] * k + prev * (1 - k);
      out.push(prev);
    }
  }
  return out;
}

export function disposeChart(chart: echarts.ECharts | null) {
  chart?.dispose();
}

export function scenarioDonutData(scenarios?: Scenario[]) {
  if (!scenarios || scenarios.length === 0) return null;
  const palette: Record<string, string> = { long: COLOR_UP, short: COLOR_DOWN, neutral: "#8a94a6" };
  return scenarios.map((s) => ({ name: s.name || s.direction, value: s.probability, color: palette[s.direction] ?? "#8a94a6" }));
}
