#!/usr/bin/env bash
# 每天一条命令：拉数据 → 出图 → 发布包。周日额外结算预测、出复盘图。
# 用法：./daily.sh            （今天）
#       ./daily.sh 2026-09-28 （指定日期）
set -e
cd "$(dirname "$0")"
DAY="${1:-$(date +%F)}"

python3 scripts/fetch_daily.py --date "$DAY"
python3 scripts/make_table_image.py --date "$DAY"

# 周日（date +%u = 7）
if [ "$(python3 -c "import datetime;print(datetime.date.fromisoformat('$DAY').isoweekday())")" = "7" ]; then
  python3 scripts/predictions.py settle
  python3 scripts/predictions.py review --date "$DAY" || true
fi

python3 scripts/make_post_pack.py --date "$DAY"
open "output/$DAY" 2>/dev/null || true   # Mac 上自动打开文件夹
