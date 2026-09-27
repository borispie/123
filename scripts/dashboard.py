"""账号数据看板：记录每条帖子数据，按栏目算互动率并排名。

记一条（发帖 48 小时后从 X 后台抄数）：
    python scripts/dashboard.py add --date 2026-09-28 --column 周一数据 --url https://x.com/.../status/123 \
        --views 5200 --likes 80 --reposts 12 --replies 9 --follows 6

也可以直接在 Excel 里编辑 data/account_stats.xlsx 的「帖子」表。

出看板：
    python scripts/dashboard.py report              # 全部数据
    python scripts/dashboard.py report --days 30    # 近 30 天

输出 output/dashboard/栏目排名.png、最佳帖子.png，并在 xlsx 里写「按栏目」汇总表。
互动率 = (点赞 + 转发 + 回复) ÷ 曝光。栏目互动率用总和算（曝光多的帖子权重大）。
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from common import DATA, OUTPUT, cell, render_table
from make_post_pack import COLUMNS

FILE = DATA / "account_stats.xlsx"
COLS = ["日期", "栏目", "链接", "曝光", "点赞", "转发", "回复", "新增粉丝"]
NUM = ["曝光", "点赞", "转发", "回复", "新增粉丝"]


def load() -> pd.DataFrame:
    if not FILE.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_excel(FILE, sheet_name="帖子")
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df[COLS]


def save(posts: pd.DataFrame, summary: pd.DataFrame | None = None):
    DATA.mkdir(exist_ok=True)
    with pd.ExcelWriter(FILE, engine="openpyxl") as w:
        posts.to_excel(w, index=False, sheet_name="帖子")
        w.sheets["帖子"].column_dimensions["C"].width = 50
        w.sheets["帖子"].freeze_panes = "A2"
        if summary is not None:
            summary.to_excel(w, index=False, sheet_name="按栏目")


def cmd_add(a):
    df = load()
    df.loc[len(df)] = [a.date, a.column, a.url, a.views, a.likes, a.reposts, a.replies, a.follows]
    save(df)
    print(f"已记录：{a.date} {a.column}，曝光 {a.views}，互动率 {(a.likes + a.reposts + a.replies) / max(a.views, 1):.2%}")


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("栏目")[NUM].sum()
    g["条数"] = df.groupby("栏目").size()
    g["互动率"] = (g["点赞"] + g["转发"] + g["回复"]) / g["曝光"].where(g["曝光"] > 0)
    g["平均曝光"] = g["曝光"] / g["条数"]
    g["平均涨粉"] = g["新增粉丝"] / g["条数"]
    g = g.sort_values("互动率", ascending=False).reset_index()
    g.insert(0, "排名", range(1, len(g) + 1))
    return g[["排名", "栏目", "条数", "平均曝光", "互动率", "平均涨粉", "曝光", "点赞", "转发", "回复", "新增粉丝"]]


def cmd_report(a):
    df = load()
    if df.empty:
        raise SystemExit(f"{FILE} 里还没有数据，先用 add 记几条")
    df["_d"] = pd.to_datetime(df["日期"]).dt.date
    span = "全部"
    if a.days:
        start = date.today() - timedelta(days=a.days)
        df = df[df["_d"] >= start]
        span = f"近 {a.days} 天"
    if df.empty:
        raise SystemExit("这个时间段没有数据")
    df["互动率"] = (df["点赞"] + df["转发"] + df["回复"]) / df["曝光"].where(df["曝光"] > 0)
    s = summarize(df)
    save(load(), s.round(4))

    avg = (df["点赞"].sum() + df["转发"].sum() + df["回复"].sum()) / max(df["曝光"].sum(), 1)
    rows = []
    for _, r in s.iterrows():
        er = r["互动率"]
        kind = None if pd.isna(er) else ("up" if er > avg else ("down" if er < avg else None))
        rows.append([cell(int(r["排名"]), align="c"), cell(r["栏目"], bold=True), cell(int(r["条数"]), align="r"),
                     cell(f"{r['平均曝光']:,.0f}", align="r"),
                     cell("—" if pd.isna(er) else f"{er:.2%}", kind, "r"),
                     cell(f"{r['平均涨粉']:,.1f}", align="r")])
    out = OUTPUT / "dashboard"
    p1 = render_table(out / "栏目排名.png", "各栏目互动率排名", ["排名", "栏目", "条数", "平均曝光", "互动率", "平均涨粉"],
                      rows, source="X 后台数据（手动记录）",
                      subtitle=f"{span}｜{len(df)} 条帖子｜整体互动率 {avg:.2%}（绿色高于整体，红色低于）",
                      col_widths=[90, 260, 110, 200, 200, 200])

    top = df.sort_values("互动率", ascending=False).head(8)
    rows = [[cell(str(r["日期"])[:10], align="c"), cell(r["栏目"]), cell(f"{r['曝光']:,.0f}", align="r"),
             cell("—" if pd.isna(r["互动率"]) else f"{r['互动率']:.2%}", align="r"),
             cell(f"{r['新增粉丝']:,.0f}", align="r")] for _, r in top.iterrows()]
    p2 = render_table(out / "最佳帖子.png", "互动率最高的帖子", ["日期", "栏目", "曝光", "互动率", "新增粉丝"], rows,
                      source="X 后台数据（手动记录）", subtitle=span, col_widths=[200, 300, 200, 200, 200])
    print(s.to_string(index=False))
    print(f"\n图：{p1}\n    {p2}\n汇总已写入 {FILE} 的「按栏目」表")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--date", default=date.today().isoformat())
    s.add_argument("--column", required=True, choices=COLUMNS)
    s.add_argument("--url", default="")
    for k in ("views", "likes", "reposts", "replies", "follows"):
        s.add_argument(f"--{k}", type=int, default=0)
    s = sub.add_parser("report")
    s.add_argument("--days", type=int)
    a = ap.parse_args()
    {"add": cmd_add, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
