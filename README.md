# Smart Trader · 智能交易分析工作台（网页版）

基于参考源码（Smart-Trader-P75）与 V3.0 全量方案重新统一设计的**纯只读分析网页应用**。
只做行情分析、情景推演、跟踪反馈，**不执行任何交易、不代管资金、不触碰账户/下单接口**。

## 启动方式

```bash
cd smart-trader-web/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```

后端同时托管前端静态产物（同源单端口部署）。启动时会后台预热 757 个现货品种行情与热门品种 K 线缓存。

## 架构

- **后端**：Python + FastAPI（141 个模块，SQLite 零配置）。数据源适配为币安现货公开接口
  `data-api.binance.vision`（受限网络实测唯一可达；OKX/Bybit 兜底不可达时诚实标记 DOWN）。
- **前端**：React 18 + TypeScript + Vite 5 + ECharts 5 + react-router-dom 6。
- **页面**：总览（Analysis Feed）/ 市场 / 报告中心 / 系统 + 品种详情页（K 线·MA·布林带·RSI/MACD·市场结构·指标快照·多空情景环形图·多周期风险地图·统一报告·历史反馈链·多交易所一致性）。

## 关键目录

- `backend/` 适配后 FastAPI 后端（`app/` 源码 + `static/` 前端产物 + `backend.log`）
- `web/` 前端源码（`npm install && npm run build` 后复制 `dist/` 到 `backend/static/`）
- 参考源码（只读，未改动）：`../source/`

## 数据源与免责声明

- 行情：Binance 现货公开数据（实时 15s 刷新）；合约/衍生品、OKX/Bybit 在受限网络下不可达，界面如实标注。
- 页面底部固定免责声明：本报告由智能系统生成，仅供信息参考，不构成投资建议。市场有风险，决策需谨慎。
- 无 placeOrder / fetchPortfolio / /orders 等任何交易或账户接口。

## 验证

- 后端 API 全部 200（runtime/status、markets 757 品种、candles、indicators、structure、scenarios、risk-map、unified-report、feedback、analysis-feed、providers/health）。
- 浏览器实测：首页真实渲染 200 个品种、上涨/下跌榜、24H 成交额；详情页 K 线与指标图表正常。
- 修复项：SPA 深层路由 fallback、ECharts 多 grid 崩溃（axis 显式 gridIndex）、bootstrap 容错（allSettled）、fetch 25s 超时、后端 K 线 TTL 缓存与启动预热、fallback 超时从 8s 降至 3s。

## P26 增强（本轮新增）

- **多源行情**：逐域探测 16 家交易所后接入 **Gate.io 现货**（`api.gateio.ws`）作为第二真实数据源。
  当前 binance + gate 双源 UP（约 2433 品种），多交易所一致性页显示真实双源共识与价差；OKX/Bybit/Yahoo 仍不可达并如实标注 DOWN。
- **P26-A 反馈归因引擎**：验证/失效原因分类 + 按多头/空头/中性分组统计（`/api/v1/p26/attribution`）。
- **P26-A 数据质量评分卡**：冻结报告字段完整性 + 数据源可用性 → 0-100 分级（`/p26/quality`）。
- **P26-A 报告审计链**：每份报告 SHA-256 冻结，SQLite append-only 版本树（`/p26/audit`，系统页展示）。
- **P26-A 预警中心**：P0/P1/P2 自动分级（真实涨跌幅异动）、同标的多条合并、免打扰时段（本地保存）。新导航页 `/alerts`。
- **P26-A 个性化 Feed**：总览页风险偏好（保守/均衡/激进）+ 自选优先排序（本地保存）。
- **P26-B 置信度校准**：Brier Score 基线 + 样本积累说明（`/p26/calibration`，未校准状态如实标注）。
- **P26-B 相似情景记忆库**：RSI 区间+MACD 方向+趋势+超买/超卖数量的结构指纹检索（`/p26/memory`）。
- **P26-B 市场状态路由**：SMA20 斜率 + ATR 占比 → 趋势/震荡/高低波动分类（`/p26/regime`，真实 K 线计算）。
- **P26-C 多情景并行跟踪**：多头/空头/中性情景独立反馈统计，互不覆盖。

详情页新增「智能增强 · P26」区块聚合展示以上全部指标。
