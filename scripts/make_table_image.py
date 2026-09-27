"""读当天 CSV，出 Excel 风格表格图到 output/日期/。

    python scripts/make_table_image.py                  # 今天，全部图
    python scripts/make_table_image.py --date 2026-09-27 --only price

出的图：
  price.png   主流币价格和涨跌
  etf.png     BTC / ETH 现货 ETF 净流入
  unlock.png  未来 7 天解锁（没有就不出）
"""
from __future__ import annotations

import argparse
from datetime import date

from common import (COINS, OUTPUT, Daily, cell, fmt_big, fmt_price, fmt_signed, pct_cell,
                    render_table, trend)


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
                        source="Tokenomist", col_widths=[220, 160, 260, 200, 260])


MAKERS = {"price": price_image, "etf": etf_image, "unlock": unlock_image}


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
