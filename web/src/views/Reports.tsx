import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../App";
import { api } from "../api";
import { Card, Badge, Chip, DirectionBadge, ConfidenceBar } from "../components";
import { REPORT_DOMAINS } from "../format";
import type { FeedItem, ReportCatalogItem } from "../types";

export default function Reports() {
  const { backendOnline, refreshTick } = useApp();
  const navigate = useNavigate();
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [reports, setReports] = useState<ReportCatalogItem[]>([]);
  const [domain, setDomain] = useState("全部");

  useEffect(() => {
    api.reportsCatalog().then((r) => setReports(r.reports ?? [])).catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    api.analysisFeed({ market: "crypto", limit: 8 }).then((r) => alive && setFeed(r.items ?? [])).catch(() => {});
    return () => {
      alive = false;
    };
  }, [refreshTick]);

  const filtered = reports.filter((r) => domain === "全部" || r.domain === domain);

  return (
    <div>
      <div className="row-between mb-14 wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>分析</h1>
          <div className="muted">真实行情 → 指标 → 结构 → 多空情景 → 历史反馈</div>
        </div>
        {backendOnline ? <Badge tone="bull">ENGINE ONLINE</Badge> : <Badge tone="warn">DATA ONLY</Badge>}
      </div>

      <div className="grid grid-3 mb-14">
        <Card title="高置信报告" sub={`15m · 独立计算`}>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{feed.length}</div>
        </Card>
        <Card title="报告目录" sub="已注册">
          <div style={{ fontSize: 26, fontWeight: 700 }}>{reports.length}</div>
        </Card>
        <Card title="当前周期" sub="切换后独立计算">
          <div style={{ fontSize: 26, fontWeight: 700 }}>15m</div>
        </Card>
      </div>

      <Card
        title="当前高置信分析"
        sub="报告冻结后，反馈只读取后续真实行情，不修改历史报告"
        right={<Badge tone="accent">{feed.length} 条</Badge>}
      >
        {feed.length === 0 ? (
          <div className="empty">
            {backendOnline ? "分析引擎当前没有返回有效报告。" : "分析后端不可达；市场数据仍可独立显示。"}
          </div>
        ) : (
          feed.slice(0, 6).map((item) => (
            <div key={item.symbol} className="feed-item" onClick={() => navigate(`/symbol/${item.symbol}`)}>
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="row">
                  <span className="sym">{item.symbol}</span>
                  <DirectionBadge direction={item.direction} />
                </div>
                {item.summary && <div className="summary">{item.summary}</div>}
                {item.feedbackSummary && (
                  <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>反馈：{item.feedbackSummary}</div>
                )}
              </div>
              <div style={{ minWidth: 120 }}>
                <ConfidenceBar value={item.confidence} />
              </div>
            </div>
          ))
        )}
      </Card>

      <Card title="报告中心" sub={`32 类报告体系 · 按域筛选 · 点击在具体品种详情中展开`}>
        <div className="row wrap mb-14">
          {REPORT_DOMAINS.map((d) => (
            <Chip key={d} active={domain === d} onClick={() => setDomain(d)}>
              {d}
            </Chip>
          ))}
        </div>
        <div className="muted mb-14" style={{ fontSize: 11 }}>
          当前筛选 {filtered.length} 项 · 详情页会对当前品种/周期逐项检查数据源并显示可用、等待或不可用
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>报告名称</th>
              <th>域</th>
              <th>优先级</th>
              <th>更新频率</th>
              <th>数据需求</th>
              <th>输出字段</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} onClick={() => navigate("/markets")} title="进入市场选择品种查看该报告">
                <td className="mono muted">{r.id}</td>
                <td className="strong">{r.name}</td>
                <td>
                  <Badge tone={r.domain === "风险" ? "bear" : r.domain === "行情" ? "accent" : "neutral"}>{r.domain}</Badge>
                </td>
                <td>
                  <Badge tone={r.priority === "P0" ? "bear" : r.priority === "P1" ? "warn" : "neutral"}>{r.priority}</Badge>
                </td>
                <td className="secondary">{r.update}</td>
                <td className="muted" style={{ fontSize: 11 }}>{(r.source_requirements || []).join("、")}</td>
                <td className="muted" style={{ fontSize: 11, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {(r.output || []).slice(0, 4).join("、")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
