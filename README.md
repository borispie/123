# X 中文币圈号 · 内容工具

「学统计的学生，用数据和概率看币圈」。每天一条命令出数据、配图和发布包。
写帖子的规则见 [CLAUDE.md](CLAUDE.md)。

## 第一次用（Mac）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

配图字体用 Noto Sans CJK SC：去 [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+SC) 下载安装。没装会自动用苹方。

可选：CoinGecko 免费 demo key，限流少一点：`export COINGECKO_API_KEY=xxx`

## 每天

```bash
./daily.sh
```

做的事：
1. `fetch_daily.py` 拉 BTC/ETH/SOL/BNB/HYPE 价格和 24h/7天/30天涨跌、ETF 净流入、未来 7 天解锁 → `data/日期.csv`
2. `make_table_image.py` 出 Excel 风格表格图 → `output/日期/*.png`
3. `make_post_pack.py` 按当天栏目生成主贴、回复、短推、一键发帖链接，并检查发帖规则 → `output/日期/发布包.md`
4. 周日额外：结算到期预测、出复盘图

拉不到的数据不会编，会写【需补充：xxx】，发布包最后会列出来。

## 每周要手动做的

| 什么时候 | 做什么 | 命令 / 文件 |
|---|---|---|
| 周日前 | 去 tokenomist.ai 把下周解锁抄进表 | `data/unlocks.csv` |
| 周日发帖时 | 记新预测 | `python scripts/predictions.py add --q "..." --p 0.35 --settle 2026-10-04 --kind above --symbol BTC --threshold 100000` |
| 非价格类预测到期 | 人工结算 | `python scripts/predictions.py settle --id 3 --result 1 --source 链接` |
| 发帖 48 小时后 | 记帖子数据 | `python scripts/dashboard.py add --column 周一数据 --views 5200 --likes 80 --reposts 12 --replies 9 --follows 6` |
| 每周 | 看哪个栏目效果好 | `python scripts/dashboard.py report --days 30` |

## 栏目

周一数据 / 周二代币经济 / 周三链上巨鲸 / 周四宏观 / 周五项目深度 / 周六统计小课 / 周日预测复盘。
模板在 `templates/`，改模板就能改帖子格式。

## 其他

- `portfolio/`：接单作品集（Pine 指标、定投回测、Hyperliquid 工具）
- `whoop/`：WHOOP 测评、教程、对比表，中英两版
- 测试：`python -m pytest tests`
