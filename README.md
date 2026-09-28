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

美债收益率要 FRED 的免费 key（fred.stlouisfed.org 注册后在 My Account → API Keys 申请）。
把下面这行加进 `~/.zshrc`，重开终端就生效：

```bash
export FRED_API_KEY=你的key
```

在云端跑的话，把 `FRED_API_KEY=你的key` 填进云端环境设置里的 Environment variables。

### 第一次跑，先确认这几样能拉到真数据

云端环境要在 Network access 里用 Custom，把这些域名加进白名单：
`*.coingecko.com`、`farside.co.uk`、`api.hyperliquid.xyz`、`*.finance.yahoo.com`、`*.llama.fi`、`defillama.com`、
`api.stlouisfed.org`、`gamma-api.polymarket.com`。Farside 在云端还是会被人机验证挡，用手填表。

第一次在 Mac 上跑，先确认这几样能拉到真数据：

```bash
python3 scripts/fetch_daily.py                     # 看最后「需补充」的清单，价格和 ETF 应该都有数
python3 portfolio/hyperliquid/hl_funding.py snapshot --top 5
python3 portfolio/backtest/dca_backtest.py --help  # 看参数，再用 BTC-USD 跑一次
```

哪一项报错，把报错整段贴给 Claude Code，一般是接口字段名要改一下。

## 每天

```bash
./daily.sh
```

做的事：
1. `fetch_daily.py` 拉 BTC/ETH/SOL/BNB/HYPE 价格和 24h/7天/30天涨跌、ETF 净流入、未来 7 天解锁、
   DefiLlama（协议收入、稳定币、TVL）、FRED（美债收益率、利率）、Polymarket（你列的市场）→ `data/日期.csv`
2. `make_table_image.py` 出 Excel 风格表格图 → `output/日期/*.png`
3. `make_post_pack.py` 按当天栏目生成主贴、回复、短推、一键发帖链接，并检查发帖规则 → `output/日期/发布包.md` 和 `发布包.json`
4. 每天结算到期的预测（当天收盘要等美东晚上 8 点以后才有，所以一般第二天早上结掉）
5. 周日额外：出复盘图

拉不到的数据不会编，会写【需补充：xxx】，发布包最后会列出来。
发布包有两份：`发布包.md` 给自己看，`发布包.json` 给发推脚本读。

默认不发推。想让它最后自动发（主贴带图 + 回复 + 短推）：

```bash
./daily.sh --post --view "如果 ETF 连续 3 天净流出，那么我会把上涨概率调低到 40%"
```

有【需补充】或者规则检查没过，就不会发，会打印原因。详见下面「自动发推」。

价格类预测按 UTC 日线收盘结算：BTC/ETH/SOL/BNB 用 Yahoo Finance，HYPE 用 CoinGecko。想让周日复盘当天就能出结果，预测的结算日就定在周六。

## 每周要手动做的

| 什么时候 | 做什么 | 命令 / 文件 |
|---|---|---|
| 周日前 | 去 tokenomist.ai 把下周解锁抄进表 | `data/unlocks.csv` |
| 想跟踪新的预测市场时 | 在 polymarket.com 找到市场，把网址 `/event/` 后面那段抄进表，再写个中文名 | `data/polymarket.csv` |
| 云端拉不到 ETF 时 | 从 farside.co.uk/btc 和 /eth 抄最近一个交易日的 Total | `data/etf_manual.csv` |
| 周日发帖时 | 记新预测：高于/低于 | `python scripts/predictions.py add --q "..." --p 0.35 --settle 2026-10-04 --kind above --symbol BTC --threshold 100000` |
| 周日发帖时 | 记新预测：区间 | `python scripts/predictions.py add --q "..." --p 0.55 --settle 2026-10-04 --kind between --symbol BTC --threshold 80000 --high 88000` |
| 周日发帖时 | 记新预测：某天收盘比另一天高 | `python scripts/predictions.py add --q "..." --p 0.6 --settle 2026-10-31 --kind up --symbol BTC --ref 2026-09-30` |
| 非价格类预测到期 | 人工结算 | `python scripts/predictions.py settle --id 3 --result 1 --source 链接` |
| 发帖 48 小时后 | 记帖子数据 | `python scripts/dashboard.py add --column 周一数据 --views 5200 --likes 80 --reposts 12 --replies 9 --follows 6` |
| 每周 | 看哪个栏目效果好 | `python scripts/dashboard.py report --days 30` |

## 自动发推（X API）

### 准备（只做一次）

1. [developer.x.com](https://developer.x.com) 里你的 App → User authentication settings → App permissions 选 **Read and write**
2. Keys and tokens 页面：拿 API Key 和 Secret；**改完权限以后**再生成 Access Token 和 Secret（改权限之前生成的 token 是只读的，发不了）
3. 开发者后台要有余额（credits），余额为 0 也发不了
4. 把 4 个 key 加进 `~/.zshrc`，重开终端：

```bash
export X_API_KEY=...
export X_API_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...
```

key 只放环境变量，不要写进仓库。脚本不会打印 key，也不会写进发布包和记录表。
在云端跑的话，把这 4 个填进环境设置的 Environment variables，Network access 白名单加 `api.x.com`。

### 用法

```bash
python scripts/post_to_x.py                                  # 预览今天的：要发什么、多少字符、带哪几张图、能不能发
python scripts/post_to_x.py --view "如果……那么……"            # 预览，把主贴里「我的看法：【需补充…】」那一行换成这句
python scripts/post_to_x.py --part short --send              # 真发：只发短推
python scripts/post_to_x.py --part main --send --view "……"   # 真发：主贴（带图）+ 挂在下面的回复
python scripts/post_to_x.py --part all --send --view "……"    # 真发：全部
python scripts/post_to_x.py --date 2026-09-27 ...            # 指定日期
```

**不加 `--send` 只预览，不会发。**

### 发之前的检查（任何一条不过就不发，打印原因）

1. 要发的部分里还有【需补充】（`--view` 能填掉「我的看法」那一行，别的要改模板或补数据后重跑 make_post_pack.py）
2. 规则检查没全部通过（禁用词、话题标签超过 2 个、持有的币没标「（我持有）」、主贴缺「不构成投资建议」、主贴有链接、hook 没数字也没问题、短推超过 280）
3. 主贴的图超过 4 张，或者图片文件不存在

只发短推时，只检查短推。

### 发的时候

- 主贴带上 `output/日期/` 里的 PNG（最多 4 张，就是 `发布包.json` 里的 `images`）。不想带的图，删掉再重跑 make_post_pack.py
- 回复挂在主贴下面，来源链接只放回复里；短推单独发
- 你有 Premium，主贴先整条发；X 说太长，就按空行自动拆成串推，每条不超过 280（中文算 2），第一条带图，回复挂在串推最后一条下面
- 网络断了或 X 服务器出错，自动重试 1 次
- 发成功的记在 `data/posted.csv`（date, part, tweet_id, url, posted_at）。同一天同一部分已经发过就跳过，不会重发。
  串推后面几条记成 `main_2`、`main_3`……。真想重发，删掉那一行
- 主贴发了、回复没发成：再跑一次只补回复，挂在已经发的主贴下面

### 报错

| 报错 | 原因 / 怎么办 |
|---|---|
| 401 / 403 | App 权限不是 Read and write；改完权限没重新生成 Access Token；余额为 0；key 填错 |
| 内容重复 | 可能上一次其实发成功了。去主页看一眼，发了就把 tweet_id 手动记进 `data/posted.csv` |
| 429 | 限流，过 15 分钟再试 |
| 缺环境变量 | 上面第 4 步，重开终端 |

## 栏目

周一数据 / 周二代币经济 / 周三链上巨鲸 / 周四宏观 / 周五项目深度 / 周六统计小课 / 周日预测复盘。
模板在 `templates/`，改模板就能改帖子格式。

## 其他

- `portfolio/`：接单作品集（Pine 指标、定投回测、Hyperliquid 工具）
- `whoop/`：WHOOP 测评、教程、对比表，中英两版
- 测试：`python -m pytest tests`
