# 作品集 / Portfolio

量化和交易工具，可接单定制。Quant & trading tools — available for custom work.

| 项目 Project | 说明 | Description |
|---|---|---|
| [`pine/smc_structure.pine`](pine/smc_structure.pine) | TradingView 指标：BOS / CHoCH、订单块、FVG，带提醒 | TradingView indicator: BOS / CHoCH, order blocks, FVGs, with alerts |
| [`backtest/dca_backtest.py`](backtest/dca_backtest.py) | 定投回测：固定定投 vs 均线加权 vs 一次性买入，含 XIRR、最大回撤、最差浮亏 | DCA backtest: fixed vs MA-weighted vs lump sum, with XIRR, max drawdown, worst unrealized loss |
| [`hyperliquid/hl_funding.py`](hyperliquid/hl_funding.py) | Hyperliquid 资金费率、OI、成交量快照和资金费率历史 | Hyperliquid funding / OI / volume snapshot and funding history |

## 用法 Usage

```bash
pip install requests pandas numpy matplotlib

# 定投回测 DCA backtest
python backtest/dca_backtest.py --ticker BTC-USD --start 2021-01-01 --amount 100 --freq W
python backtest/dca_backtest.py --ticker GC=F --start 2015-01-01 --freq M   # 黄金 gold

# Hyperliquid
python hyperliquid/hl_funding.py snapshot --top 20 --sort funding
python hyperliquid/hl_funding.py history --coin HYPE --days 30
```

Pine 指标：TradingView → Pine 编辑器 → 粘贴 → 添加到图表。
Pine: TradingView → Pine Editor → paste → Add to chart.

## 可定制 Custom work

- Pine Script 指标和策略（含回测、提醒）/ Pine Script indicators & strategies
- Python 回测脚本（任意资产、任意规则）/ Python backtests for any asset and rule set
- 链上 / 交易所数据工具（Hyperliquid、CEX API）/ On-chain & exchange data tools
- 统计辅导（R、Python、概率论）/ Statistics tutoring (R, Python, probability)

联系 Contact：【需补充：X 账号 / 邮箱】
