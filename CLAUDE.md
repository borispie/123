# 关于我（Siyi）

- Penn State 大四，计算统计专业。深圳人，英语不是母语。
- 2026 年 5–8 月在新加坡 Insight Capital 做量化分析实习（风险建模、组合优化）。
- 电脑是 macOS。常用 Python、R、R Markdown。
- 喜欢的方向：数据和量化、代币经济（HYPE、BNB、OKB 的解锁、回购、FDV）、交易和市场结构（SMC/BMS、订单块、FVG）、定投（BTC、黄金、HYPE，第一原则是不能全亏）。

# 我在做的事

1. **X 中文币圈号（主线）**：定位是「学统计的学生，用数据和概率看币圈」。每天发，目标是拿到 X 创作者收益。
2. **YouTube / TikTok AI 视频**：国内跑通过连载式 AI 视频，现在要改成面向海外观众。
3. **闲鱼 WHOOP 业务**：卖表带、代办会员续费、指导设置，启动资金约 1 万人民币。
4. **接技术小活**（还没开始）：统计辅导、Pine Script 指标、回测脚本、Hyperliquid 数据工具。

# 和我合作的方式

- 回复用中文，简短、直白，像学生说话，不要写成专业报告腔。
- 直接给做好的东西（文件、图、能发的文案），不要只给步骤让我自己做。
- 改动之前不用问我小事，做完告诉我改了什么就行。

# X 内容规则（写帖子时必须遵守）

- **数字只用脚本或网页真实查到的**，不能编。查不到就写【需补充：xxx】。每个数字都要能说出来源。
- 不写「必涨」「必跌」「稳了」。判断用概率或者「如果……那么……」。
- 提到我持有的币，加「（我持有）」。主贴结尾加「不构成投资建议」。
- 话题标签一条最多 2 个，cashtag 用 $BTC 这种格式。来源链接放在回复里，不放主贴。
- 主贴前两行是 hook：一个反常识的数字，或者一个问题。
- 每周栏目：周一数据 / 周二代币经济 / 周三链上巨鲸 / 周四宏观 / 周五项目深度 / 周六统计小课 / 周日预测复盘。
- 每周日发 1–3 个带概率的预测，结算后用 Brier 分数 =（概率 − 结果）² 打分，记录在 `data/predictions.xlsx`。

# 常用数据源

CoinGecko（价格）、DefiLlama（TVL、收入、回购）、Farside（ETF 流入）、Tokenomist（解锁）、CoinGlass（资金费率、OI、爆仓）、Yahoo Finance（历史日线）、returnsview.com（BTC 月度收益）、Newsquawk（宏观日历）。

# 配图风格

- 表格图做成 Excel 截图的样子：上面一行列字母 A B C，左边一列行号，灰色网格线。
- 表头深蓝底白字（#1F4E78）。涨 = 浅绿底深绿字（#C6EFCE / #006100），跌 = 浅红底深红字（#FFC7CE / #9C0006），数字前面一定带 + / − 号。
- 字体 Noto Sans CJK SC，宽 1200px，2 倍分辨率导出 PNG。高度不超过 1500px，这样手机上不会被裁掉。
- 图片最下面一行写数据来源和「不构成投资建议」。
- 用 Python + Playwright 把 HTML 渲染成 PNG。

# 建议的文件夹结构

```
x-content/
├── CLAUDE.md
├── scripts/        # 拉数据、算数、出图、生成发布包的脚本
├── data/           # 每天的 CSV、predictions.xlsx、账号数据表
├── output/2026-09-27/   # 每天一个文件夹：图片 + 发布包.md
└── templates/      # 每个栏目的文案模板
```

# 要做的项目（按先后）

1. `scripts/fetch_daily.py`：一条命令拉 BTC、ETH、SOL、BNB、HYPE 价格和近 7/30 天涨跌、ETF 每日流入、下周解锁，存到 `data/YYYY-MM-DD.csv`。
2. `scripts/make_table_image.py`：读 CSV，按上面的配图风格出 PNG。
3. `scripts/predictions.py`：更新预测记录，到结算日自动填结果、算 Brier 分数，出周日复盘图。
4. `scripts/make_post_pack.py`：按当天栏目模板生成主贴、回复、短推、一键发帖链接（x.com/intent/post），存成 `output/日期/发布包.md`。
5. 账号数据看板：记录每条帖子的曝光、点赞、转发、回复、新增粉丝，按栏目算互动率并排名。
6. 接单作品集：Pine Script 指标、回测脚本、Hyperliquid 数据工具，放到 GitHub。
7. WHOOP 内容：测评和教程的脚本、对比表，中英两版。
