"""定投回测：固定定投 vs 均线加权定投 vs 一次性买入。

    python dca_backtest.py --ticker BTC-USD --start 2021-01-01 --amount 100 --freq W
    python dca_backtest.py --ticker GC=F --start 2015-01-01          # 黄金期货
    python dca_backtest.py --csv my_prices.csv                       # 自己的数据（列：Date, Close）

策略：
  fixed   每期固定买 amount
  ma      价格低于 200 日均线买 2 倍，高于买 0.5 倍（「越跌越买」）
  lump    第一天把 fixed 的总投入一次性买入

指标：总投入、期末市值、收益率、年化（XIRR）、最大回撤、最差时的浮亏比例。
「最差浮亏」对应「不能全亏」原则：看最惨的时候本金亏了多少。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"


def load_yahoo(ticker: str, start: str) -> pd.Series:
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp())
    r = requests.get(YAHOO.format(t=ticker), params={"period1": p1, "period2": p2, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
    close = res["indicators"]["quote"][0]["close"]
    return pd.Series(close, index=idx, name="close").dropna()


def load_csv(path: str) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    return df["Close"].astype(float).rename("close").dropna()


def schedule(prices: pd.Series, freq: str) -> pd.DatetimeIndex:
    """每期第一个有价格的日子。"""
    return prices.groupby(prices.index.to_period(freq)).head(1).index


def run(prices: pd.Series, amount: float, freq: str, strategy: str) -> pd.DataFrame:
    buy_days = schedule(prices, freq)
    ma = prices.rolling(200, min_periods=50).mean()
    buys = pd.Series(0.0, index=prices.index)
    if strategy == "fixed":
        buys[buy_days] = amount
    elif strategy == "ma":
        mult = np.where(prices[buy_days] < ma[buy_days].fillna(np.inf), 2.0, 0.5)
        buys[buy_days] = amount * mult
    elif strategy == "lump":
        buys.iloc[0] = amount * len(buy_days)
    units = (buys / prices).cumsum()
    out = pd.DataFrame({"price": prices, "invested": buys.cumsum(), "cash_in": buys})
    out["value"] = units * prices
    return out


def xirr(flows: list[tuple[pd.Timestamp, float]]) -> float:
    """二分法求年化内部收益率。flows：(日期, 金额)，投入为负。"""
    t0 = flows[0][0]
    yrs = np.array([(d - t0).days / 365.25 for d, _ in flows])
    amt = np.array([a for _, a in flows])
    npv = lambda r: np.sum(amt / (1 + r) ** yrs)
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return mid


def stats(df: pd.DataFrame) -> dict:
    inv, val = df["invested"].iloc[-1], df["value"].iloc[-1]
    dd = (df["value"] / df["value"].cummax() - 1).min()
    pnl_pct = (df["value"] / df["invested"].where(df["invested"] > 0) - 1)
    flows = [(d, -a) for d, a in df["cash_in"].items() if a > 0] + [(df.index[-1], val)]
    return {"总投入": inv, "期末市值": val, "收益率": val / inv - 1, "年化XIRR": xirr(flows),
            "最大回撤": dd, "最差浮亏": pnl_pct.min()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="BTC-USD")
    ap.add_argument("--csv")
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--amount", type=float, default=100)
    ap.add_argument("--freq", default="W", choices=["D", "W", "M"], help="D 每天 / W 每周 / M 每月")
    ap.add_argument("--plot", default="dca_result.png")
    a = ap.parse_args()

    prices = load_csv(a.csv) if a.csv else load_yahoo(a.ticker, a.start)
    prices = prices[prices.index >= a.start]
    name = Path(a.csv).stem if a.csv else a.ticker
    results = {s: run(prices, a.amount, a.freq, s) for s in ("fixed", "ma", "lump")}
    table = pd.DataFrame({s: stats(df) for s, df in results.items()}).T
    table.index = ["固定定投", "均线加权定投", "一次性买入"]

    fmt = table.copy()
    for c in ("总投入", "期末市值"):
        fmt[c] = table[c].map("${:,.0f}".format)
    for c in ("收益率", "年化XIRR", "最大回撤", "最差浮亏"):
        fmt[c] = table[c].map("{:+.1%}".format)
    print(f"{name}  {prices.index[0].date()} ~ {prices.index[-1].date()}  每{ {'D': '天', 'W': '周', 'M': '月'}[a.freq] } ${a.amount:,.0f}")
    print(fmt.to_string())

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "PingFang SC", "Arial Unicode MS", "sans-serif"]
        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        for (s, df), label in zip(results.items(), table.index):
            ax.plot(df.index, df["value"], label=label)
        ax.plot(results["fixed"].index, results["fixed"]["invested"], "k--", lw=1, label="固定定投累计投入")
        ax.set_title(f"{name} 定投回测")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(a.plot)
        print(f"图：{a.plot}")
    except ImportError:
        print("没装 matplotlib，跳过画图")


if __name__ == "__main__":
    main()
