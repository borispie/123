"""Hyperliquid 永续数据工具：资金费率、持仓量（OI）、成交量。用的是官方公开 API，不用 key。

    python hl_funding.py snapshot                 # 全市场快照，按 OI 排序，存 CSV
    python hl_funding.py snapshot --top 20 --sort funding
    python hl_funding.py history --coin HYPE --days 30   # 某个币近 N 天资金费率

说明：
  - Hyperliquid 资金费率每小时结算一次，API 返回的是「每小时费率」。
  - 年化 = 每小时费率 × 24 × 365。正数 = 多头付钱给空头。
  - OI 在 API 里是币的数量，这里乘标记价格换成美元。
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import pandas as pd
import requests

API = "https://api.hyperliquid.xyz/info"
HOURS_PER_YEAR = 24 * 365


def post(body: dict):
    for i in range(3):
        try:
            r = requests.post(API, json=body, timeout=20)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == 2:
                raise
            time.sleep(2 ** i)


def parse_snapshot(data) -> pd.DataFrame:
    meta, ctxs = data
    rows = []
    for asset, c in zip(meta["universe"], ctxs):
        if asset.get("isDelisted"):
            continue
        mark = float(c["markPx"]) if c.get("markPx") else None
        prev = float(c["prevDayPx"]) if c.get("prevDayPx") else None
        oi = float(c["openInterest"]) if c.get("openInterest") else 0.0
        f = float(c["funding"]) if c.get("funding") else 0.0
        rows.append({
            "币种": asset["name"],
            "标记价格": mark,
            "24h涨跌%": (mark / prev - 1) * 100 if mark and prev else None,
            "每小时资金费率%": f * 100,
            "年化资金费率%": f * HOURS_PER_YEAR * 100,
            "OI(美元)": oi * mark if mark else None,
            "24h成交额(美元)": float(c.get("dayNtlVlm") or 0),
            "最大杠杆": asset.get("maxLeverage"),
        })
    return pd.DataFrame(rows)


def cmd_snapshot(a):
    df = parse_snapshot(post({"type": "metaAndAssetCtxs"}))
    key = {"oi": "OI(美元)", "funding": "年化资金费率%", "volume": "24h成交额(美元)"}[a.sort]
    df = df.sort_values(key, ascending=False, key=abs if a.sort == "funding" else None)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = f"hl_snapshot_{ts}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    show = df.head(a.top).copy()
    for c in ("OI(美元)", "24h成交额(美元)"):
        show[c] = show[c].map(lambda x: f"${x / 1e6:,.1f}M" if pd.notna(x) else "—")
    print(f"Hyperliquid 快照 {ts} UTC（来源：{API}）")
    print(show.round(4).to_string(index=False))
    print(f"\n全部 {len(df)} 个币已存 {path}")


def cmd_history(a):
    start = int((time.time() - a.days * 86400) * 1000)
    rows, cursor = [], start
    while True:  # 一次最多返回 500 条，翻页
        batch = post({"type": "fundingHistory", "coin": a.coin, "startTime": cursor})
        if not batch:
            break
        rows += batch
        cursor = batch[-1]["time"] + 1
        if len(batch) < 500:
            break
    if not rows:
        raise SystemExit(f"{a.coin} 没有资金费率数据，检查币名（区分大小写，如 HYPE、BTC）")
    df = pd.DataFrame(rows)
    df["时间"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["费率%"] = df["fundingRate"].astype(float) * 100
    daily = df.set_index("时间")["费率%"].resample("D").sum()  # 每天 24 次加总 = 日费率
    path = f"hl_funding_{a.coin}_{a.days}d.csv"
    df[["时间", "费率%"]].to_csv(path, index=False, encoding="utf-8-sig")
    mean_h = df["费率%"].mean()
    print(f"{a.coin} 近 {a.days} 天资金费率（{len(df)} 次结算）")
    print(f"  平均每小时 {mean_h:+.4f}%  → 年化 {mean_h * HOURS_PER_YEAR:+.1f}%")
    print(f"  正费率占比 {(df['费率%'] > 0).mean():.0%}")
    print(f"  日费率最高 {daily.max():+.3f}%（{daily.idxmax().date()}），最低 {daily.min():+.3f}%（{daily.idxmin().date()}）")
    print(f"明细已存 {path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--top", type=int, default=15)
    s.add_argument("--sort", choices=["oi", "funding", "volume"], default="oi")
    s = sub.add_parser("history")
    s.add_argument("--coin", required=True)
    s.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    {"snapshot": cmd_snapshot, "history": cmd_history}[a.cmd](a)


if __name__ == "__main__":
    main()
