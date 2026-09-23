from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class ReportDefinition:
    id: int
    key: str
    name: str
    domain: str
    priority: str
    update: str
    markets: tuple[str, ...]
    source_requirements: tuple[str, ...]

REPORTS = [
(1,"realtime_market","实时行情速览","行情","P0","秒级",("crypto","us","hk","commodities"),("quote",)),
(2,"preopen_intraday","盘前/盘中快评","行情","P1","盘前/盘中",("us","hk","crypto"),("quote","session")),
(3,"probability","概率判断报告","研究","P1","盘中/每日",("crypto","us","hk","commodities"),("technical",)),
(4,"entry_scenario","开仓情景分析","行情","P0","信号触发",("crypto","us","hk","commodities"),("technical","risk")),
(5,"holding_risk","持仓管理/风控报告","风险","P0","实时/定时",("crypto","us","hk","commodities"),("technical","risk")),
(6,"bull_bear_battle","多空博弈专题","资金","P1","小时级",("crypto","us","hk"),("funding","flow")),
(7,"comparison","综合对比报告","研究","P2","用户触发",("crypto","us","hk","commodities"),("quote","fundamental")),
(8,"technical","技术面分析","技术","P1","实时/定时",("crypto","us","hk","commodities"),("ohlcv",)),
(9,"money_flow","资金面与筹码分析","资金","P1","实时",("crypto","us","hk"),("flow",)),
(10,"market_signal","盘面信号解析","行情","P0","实时",("crypto","us","hk","commodities"),("quote","ohlcv")),
(11,"catalyst","催化剂与事件驱动","事件","P1","事件触发",("crypto","us","hk","commodities"),("news","events")),
(12,"fundamental_institution","基本面与机构观点","基本面","P1","季度/事件",("us","hk"),("fundamental",)),
(13,"news_sentiment","新闻与舆情","事件","P2","实时",("crypto","us","hk","commodities"),("news","sentiment")),
(14,"observation_nodes","观察节点","行情","P0","每日",("crypto","us","hk","commodities"),("technical","calendar")),
(15,"risk_warning","风险提示","风险","P0","每日/事件",("crypto","us","hk","commodities"),("risk",)),
(16,"cross_market","换算与跨市场对比","基本面","P2","实时",("crypto","us","hk","commodities"),("fx","quote")),
(17,"one_line_summary","一句话总结","行情","P0","每次报告",("crypto","us","hk","commodities"),("report",)),
(18,"mtf_resonance","多周期共振报告","技术","P2","盘中/每日",("crypto","us","hk","commodities"),("ohlcv_mtf",)),
(19,"divergence","背离信号报告","技术","P2","实时",("crypto","us","hk","commodities"),("ohlcv_mtf",)),
(20,"patterns","缺口与形态报告","技术","P2","实时/每日",("crypto","us","hk","commodities"),("ohlcv",)),
(21,"volume_price","量价关系报告","技术","P2","实时",("crypto","us","hk","commodities"),("ohlcv",)),
(22,"volatility","波动率报告","技术","P2","每日",("crypto","us","hk","commodities"),("ohlcv",)),
(23,"onchain","链上数据报告","研究","P2","小时/每日",("crypto",),("onchain",)),
(24,"funding_basis","资金费率与基差报告","资金","P2","实时",("crypto","commodities"),("derivatives",)),
(25,"sentiment","情绪指标报告","风险","P1","实时/每日",("crypto","us","hk","commodities"),("sentiment",)),
(26,"correlation","相关性分析报告","研究","P2","每周",("crypto","us","hk","commodities"),("historical",)),
(27,"event_calendar","事件日历报告","事件","P1","每日",("crypto","us","hk","commodities"),("calendar",)),
(28,"arbitrage","套利机会报告","研究","P2","实时/每日",("crypto","commodities"),("derivatives","quote")),
(29,"strategy_backtest","策略研究报告","研究","P2","用户触发",("crypto","us","hk","commodities"),("historical","strategy")),
(30,"holding_diagnosis","持仓诊断报告","风险","P2","每日/触发",("crypto","us","hk","commodities"),("observation","technical")),
(31,"behavior_review","交易行为复盘报告","复盘","P2","每周/每月",("crypto","us","hk","commodities"),("journal",)),
(32,"smart_alert","智能预警分级报告","风险","P0","实时",("crypto","us","hk","commodities"),("events","risk")),
]

REGISTRY = {x[1]: ReportDefinition(x[0], *x[1:]) for x in REPORTS}
SCENES = {
    "pre_market": [2,27,6,25,17],
    "intraday": [1,10,9,21,32],
    "post_market": [30,31,17,14],
    "deep_research": [8,12,23,26,29],
    "event_driven": [11,27,15,4],
    "all": list(range(1,33)),
}

def catalog() -> dict[str, Any]:
    return {"count": len(REPORTS), "reports": [asdict(v) for v in REGISTRY.values()], "scenes": SCENES}
