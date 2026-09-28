"""读当天 CSV，出 Excel 风格表格图到 output/日期/。

    python scripts/make_table_image.py                  # 今天，全部图
    python scripts/make_table_image.py --date 2026-09-27 --only price

出的图：
  price.png   主流币价格和涨跌
  etf.png     BTC / ETH 现货 ETF 净流入
  unlock.png  未来 7 天解锁（没有就不出）
  rank_7d.png 近 7 天强弱排行（横向条形图，涨绿跌红）
  fdv.png     还有多少币没放出来（流通市值 ÷ FDV）
"""
from __future__ import annotations

import argparse
from datetime import date

import html

from common import (COINS, DISCLAIMER, OUTPUT, Daily, cell, fmt_big, fmt_pct, fmt_price, fmt_signed, pct_cell,
                    render_png, render_table, trend)

# ---------- 条形图（和表格同一套颜色） ----------

BAR_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", sans-serif; color: #1a1a1a; }
#root { width: 1200px; background: #fff; padding: 28px 28px 20px; }
h1 { font-size: 30px; font-weight: 700; margin-bottom: 6px; }
.sub { font-size: 17px; color: #666; margin-bottom: 22px; }
.chart { border: 1px solid #d4d4d4; padding: 18px 20px 10px; }
.row { display: flex; align-items: center; height: 58px; }
.name { width: 110px; font-size: 22px; font-weight: 700; }
.track { position: relative; flex: 1; height: 34px; }
.bar { position: absolute; top: 0; height: 34px; border-radius: 4px; }
.up { background: #C6EFCE; border: 1px solid #63BE7B; }
.down { background: #FFC7CE; border: 1px solid #F8696B; }
.done { background: #1F4E78; }
.left { background: #F2F2F2; border: 1px solid #d4d4d4; }
.zero { position: absolute; top: -8px; bottom: -8px; width: 2px; background: #9a9a9a; }
.val { width: 250px; text-align: right; font-size: 21px; font-variant-numeric: tabular-nums; }
.val.upc { color: #006100; } .val.downc { color: #9C0006; }
.key { font-size: 16px; color: #555; margin: 10px 0 0 110px; }
.key span { display: inline-block; width: 14px; height: 14px; vertical-align: -2px; margin: 0 6px 0 18px; border-radius: 2px; }
.foot { margin-top: 14px; font-size: 16px; color: #666; display: flex; justify-content: space-between; }
"""


def bar_page(title: str, subtitle: str, rows_html: str, source: str, key_html: str = "") -> str:
    e = html.escape
    return (f"<html><head><meta charset='utf-8'><style>{BAR_CSS}</style></head><body><div id='root'>"
            f"<h1>{e(title)}</h1><div class='sub'>{e(subtitle)}</div>"
            f"<div class='chart'>{rows_html}{key_html}</div>"
            f"<div class='foot'><span>数据来源：{e(source)}</span><span>{DISCLAIMER}</span></div>"
            "</div></body></html>")


def rank_7d_image(d: Daily, out_dir):
    """近 7 天涨跌排行：零线在中间，涨往右（绿）、跌往左（红），按涨幅从高到低。"""
    vals = {s: d.v("price", s, "chg_7d") for s in COINS}
    vals = {s: v for s, v in vals.items() if v is not None}
    if len(vals) < 2:
        return None
    m = max(abs(v) for v in vals.values()) or 1
    rows = []
    for s, v in sorted(vals.items(), key=lambda kv: -kv[1]):
        w = abs(v) / m * 48  # 每边最多 48%
        left = 50 if v >= 0 else 50 - w
        cls = "up" if v >= 0 else "down"
        rows.append(f"<div class='row'><div class='name'>{s}</div><div class='track'>"
                    f"<div class='bar {cls}' style='left:{left:.2f}%;width:{w:.2f}%'></div>"
                    f"<div class='zero' style='left:50%'></div></div>"
                    f"<div class='val {cls}c'>{fmt_pct(v)}</div></div>")
    ref = next((d.ref_date("price", s, "chg_7d") for s in vals if d.ref_date("price", s, "chg_7d")), d.day)
    best, worst = max(vals, key=vals.get), min(vals, key=vals.get)
    title = f"近 7 天：{best} 最强，{worst} 最弱"
    return render_png(bar_page(title, f"主流币 7 天涨跌幅，按涨幅排序｜数据时间 {ref}（UTC）", "".join(rows), "CoinGecko"),
                      out_dir / "rank_7d.png")


def fdv_image(d: Daily, out_dir):
    """流通市值 ÷ FDV = 已经放出来的比例。深蓝 = 已流通，灰 = 还没放出来。"""
    share = {}
    for s in COINS:
        mc, fdv = d.v("price", s, "market_cap"), d.v("price", s, "fdv")
        if mc and fdv:
            share[s] = min(mc / fdv, 1.0)
    if len(share) < 2:
        return None
    rows = []
    for s, r in sorted(share.items(), key=lambda kv: kv[1]):
        rest = 1 - r
        rows.append(f"<div class='row'><div class='name'>{s}</div><div class='track'>"
                    f"<div class='bar done' style='left:0;width:{r * 100:.2f}%'></div>"
                    + (f"<div class='bar left' style='left:{r * 100:.2f}%;width:{rest * 100:.2f}%'></div>" if rest > 0.005 else "")
                    + f"</div><div class='val'>还没放出 {rest * 100:.0f}%</div></div>")
    key = "<div class='key'><span style='background:#1F4E78'></span>已流通<span style='background:#F2F2F2;border:1px solid #d4d4d4'></span>还没放出来</div>"
    most = min(share, key=share.get)
    title = f"{most} 还有 {(1 - share[most]) * 100:.0f}% 的币没放出来"
    ref = d.ref_date("price", most, "fdv") or d.day
    return render_png(bar_page(title, f"流通市值 ÷ 完全稀释估值（FDV）｜数据时间 {ref}（UTC）", "".join(rows),
                                "CoinGecko（FDV 按当前总供应量算，不含 BTC 还没挖出来的部分）", key),
                      out_dir / "fdv.png")


def price_image(d: Daily, out_dir):
    rows = []
    for sym in COINS:
        rows.append([
            cell(sym, bold=True, align="c"),
            cell(fmt_price(d.v("price", sym, "price")), align="r"),
            pct_cell(d.v("price", sym, "chg_24h")),
            pct_cell(d.v("price", sym, "chg_7d")),
            pct_cell(d.v("price", sym, "chg_30d")),
            cell(fmt_big(d.v("price", sym, "market_cap")), align="r"),
            cell(fmt_big(d.v("price", sym, "fdv")), align="r"),
        ])
    ref = next((d.ref_date("price", s, "price") for s in COINS if d.ref_date("price", s, "price")), d.day)
    return render_table(out_dir / "price.png", "主流币涨跌一览",
                        ["币种", "价格", "24小时", "7天", "30天", "市值", "FDV"], rows,
                        source="CoinGecko", subtitle=f"数据时间：{ref}（UTC）",
                        col_widths=[120, 170, 150, 150, 150, 180, 180])


def etf_image(d: Daily, out_dir):
    rows = []
    for sym, name in (("BTC", "比特币现货 ETF"), ("ETH", "以太坊现货 ETF")):
        v = d.v("etf", sym, "etf_net_flow")
        rows.append([
            cell(name, bold=True),
            cell(d.ref_date("etf", sym, "etf_net_flow") or "—", align="c"),
            cell(fmt_signed(v, unit=" 百万美元"), trend(v), "r"),
        ])
    return render_table(out_dir / "etf.png", "美国现货 ETF 净流入",
                        ["产品", "交易日", "净流入"], rows, source="Farside Investors",
                        subtitle="最近一个有数据的交易日", col_widths=[420, 320, 360])


def unlock_image(d: Daily, out_dir):
    u = d.rows("unlock")
    u = u[u.metric != "none"]
    if u.empty:
        return None
    rows = []
    for (day, sym), g in u.groupby(["ref_date", "symbol"], sort=True):
        get = lambda m: next((r["value"] for _, r in g.iterrows() if r["metric"] == m), "")
        amt, pct, usd = get("amount"), get("pct_circulating"), get("value_usd")
        rows.append([
            cell(day, align="c"), cell(sym, bold=True, align="c"),
            cell(f"{float(amt):,.0f}" if amt else "需补充", align="r"),
            cell(f"{float(pct):.2f}%" if pct else "需补充", align="r"),
            cell(fmt_big(float(usd)) if usd else "需补充", align="r"),
        ])
    return render_table(out_dir / "unlock.png", "未来 7 天代币解锁",
                        ["日期", "代币", "解锁数量", "占流通", "价值"], rows,
                        source=" / ".join(dict.fromkeys(u["source"])) or "Tokenomist",
                        col_widths=[220, 160, 260, 200, 260])


MAKERS = {"price": price_image, "etf": etf_image, "unlock": unlock_image,
          "rank_7d": rank_7d_image, "fdv": fdv_image}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--only", choices=list(MAKERS))
    args = ap.parse_args()

    d = Daily(args.date)
    out_dir = OUTPUT / args.date
    for name, fn in MAKERS.items():
        if args.only and name != args.only:
            continue
        p = fn(d, out_dir)
        print(f"{name}: {p or '没有数据，跳过'}")


if __name__ == "__main__":
    main()
