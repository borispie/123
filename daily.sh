#!/usr/bin/env bash
# 每天一条命令：拉数据 → 出图 → 发布包。周日额外结算预测、出复盘图。默认不发推。
# 用法：./daily.sh                          （今天）
#       ./daily.sh 2026-09-28               （指定日期）
#       ./daily.sh --post                   （最后自动发推：主贴带图 + 回复 + 短推）
#       ./daily.sh --post --view "一句话"   （顺便把主贴里「我的看法：【需补充…】」换成这句）
set -e
cd "$(dirname "$0")"
DAY="$(date +%F)"
POST=0
VIEW=""
while [ $# -gt 0 ]; do
  case "$1" in
    --post) POST=1 ;;
    --view) VIEW="$2"; shift ;;
    *) DAY="$1" ;;
  esac
  shift
done

python3 scripts/fetch_daily.py --date "$DAY"
python3 scripts/make_table_image.py --date "$DAY"

# 每天都结算一次：收盘价要等次日 00:00 UTC（美东晚 8 点）才有，到期的预测第二天自动结掉
python3 scripts/predictions.py settle || true

# 周日（isoweekday = 7）出复盘图
if [ "$(python3 -c "import datetime;print(datetime.date.fromisoformat('$DAY').isoweekday())")" = "7" ]; then
  python3 scripts/predictions.py review --date "$DAY" || true
fi

python3 scripts/make_post_pack.py --date "$DAY"
open "output/$DAY" 2>/dev/null || true   # Mac 上自动打开文件夹

# 加了 --post 才发。检查不过（还有【需补充】等）会打印原因，不会发
if [ "$POST" = 1 ]; then
  if [ -n "$VIEW" ]; then
    python3 scripts/post_to_x.py --date "$DAY" --part all --send --view "$VIEW"
  else
    python3 scripts/post_to_x.py --date "$DAY" --part all --send
  fi
fi
