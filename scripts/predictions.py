"""预测记录 + Brier 打分，记录存在 data/predictions.xlsx。

加预测（周日发帖时）：
    python scripts/predictions.py add --q "BTC 10/4 收盘高于 10 万美元" --p 0.35 \
        --settle 2026-10-04 --kind above --symbol BTC --threshold 100000
    python scripts/predictions.py add --q "BTC 10/4 收盘在 8 万到 8.8 万之间" --p 0.55 \
        --settle 2026-10-04 --kind between --symbol BTC --threshold 80000 --high 88000
    python scripts/predictions.py add --q "BTC 10 月收涨" --p 0.6 \
        --settle 2026-10-31 --kind up --symbol BTC --ref 2026-09-30       # 10/31 收盘 > 9/30 收盘
    python scripts/predictions.py add --q "美联储 10 月降息" --p 0.6 --settle 2026-10-29   # 人工结算

结算：
    python scripts/predictions.py settle                 # 自动结算到期的价格类预测
    python scripts/predictions.py settle --id 3 --result 1 --source https://...   # 人工结算

周日复盘图：
    python scripts/predictions.py review --date 2026-10-04

规则：
  - 价格类用结算日的 UTC 日线收盘价：BTC/ETH/SOL/BNB 用 Yahoo Finance（和帖子里写的结算依据一致），
    拉不到或没有 Yahoo 代码的币（HYPE）用 CoinGecko「次日 00:00 UTC」快照价。
  - 当天的收盘要等次日 00:00 UTC（美东晚上 8 点）才有，所以 daily.sh 每天都跑一次 settle。
  - Brier = (概率 − 结果)²，结果 1 = 发生，0 = 没发生。越低越好，全猜 50% 是 0.25。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from common import COINS, DATA, OUTPUT, cell, coingecko_headers, get, render_table

FILE = DATA / "predictions.xlsx"
COLS = ["id", "发布日期", "结算日期", "问题", "类型", "币种", "阈值", "阈值上限", "参考日期", "概率",
        "结果", "结算值", "结算来源", "Brier", "状态"]
PRICE_KINDS = ("above", "below", "between", "up")
YAHOO_TICKERS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "BNB": "BNB-USD"}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
PENDING, DONE = "待结算", "已结算"
BASELINE = 0.25


def brier(p: float, outcome: int) -> float:
    return round((p - outcome) ** 2, 4)


def load() -> pd.DataFrame:
    if not FILE.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_excel(FILE, dtype={"id": "Int64"})
    for c in COLS:
        if c not in df:
            df[c] = None
    return df[COLS]


def save(df: pd.DataFrame):
    DATA.mkdir(exist_ok=True)
    with pd.ExcelWriter(FILE, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="predictions")
        ws = w.sheets["predictions"]
        widths = {"A": 5, "B": 12, "C": 12, "D": 40, "E": 8, "F": 7, "G": 11, "H": 11, "I": 12,
                  "J": 7, "K": 6, "L": 12, "M": 40, "N": 8, "O": 8}
        for col, wd in widths.items():
            ws.column_dimensions[col].width = wd
        ws.freeze_panes = "A2"


def cmd_add(a):
    if not 0 <= a.p <= 1:
        raise SystemExit("概率要在 0 到 1 之间，比如 0.35")
    kind = a.kind or "manual"
    if kind in ("above", "below", "between") and (not a.symbol or a.threshold is None):
        raise SystemExit("价格类预测要给 --symbol 和 --threshold")
    if kind == "between" and (a.high is None or a.high <= a.threshold):
        raise SystemExit("区间预测要给 --high，且要大于 --threshold（下限）")
    if kind == "up" and (not a.symbol or not a.ref):
        raise SystemExit("涨跌预测要给 --symbol 和 --ref（拿哪天的收盘比，比如 2026-09-30）")
    if a.symbol and a.symbol.upper() not in COINS:
        raise SystemExit(f"币种只支持 {list(COINS)}，别的用人工结算")
    df = load()
    new_id = 1 if df.empty else int(df["id"].max()) + 1
    df.loc[len(df)] = {
        "id": new_id, "发布日期": a.date, "结算日期": a.settle, "问题": a.q, "类型": kind,
        "币种": (a.symbol or "").upper() or None, "阈值": a.threshold, "阈值上限": a.high,
        "参考日期": a.ref, "概率": a.p,
        "结果": None, "结算值": None, "结算来源": None, "Brier": None, "状态": PENDING,
    }
    save(df)
    print(f"已加 #{new_id}：{a.q}（{a.p:.0%}，{a.settle} 结算）")


def yahoo_close(ticker: str, day: date) -> float:
    """Yahoo 日线（UTC）里 day 那一根的收盘价。"""
    p1 = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    r = get(YAHOO_CHART.format(t=ticker),
            params={"period1": p1 - 86400, "period2": p1 + 2 * 86400, "interval": "1d"}).json()
    res = r["chart"]["result"][0]
    for ts, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if datetime.fromtimestamp(ts, timezone.utc).date() == day and c is not None:
            return float(c)
    raise ValueError(f"Yahoo 没有 {ticker} {day} 的日线")


def coingecko_close(symbol: str, day: date) -> float:
    """CoinGecko 在 day 次日 00:00 UTC 的快照价，约等于 day 的收盘。"""
    snap = day + timedelta(days=1)
    r = get(f"https://api.coingecko.com/api/v3/coins/{COINS[symbol]}/history",
            params={"date": snap.strftime("%d-%m-%Y"), "localization": "false"},
            headers=coingecko_headers()).json()
    return float(r["market_data"]["current_price"]["usd"])


def close_price(symbol: str, day: date) -> tuple[float, str]:
    """结算日 UTC 收盘价 + 来源链接。先 Yahoo，拉不到再用 CoinGecko。"""
    t = YAHOO_TICKERS.get(symbol)
    if t:
        try:
            return yahoo_close(t, day), f"https://finance.yahoo.com/quote/{t}/history/（{day} 收盘）"
        except Exception as e:
            print(f"  Yahoo 拉 {symbol} {day} 失败，改用 CoinGecko：{e}")
    snap = (day + timedelta(days=1)).strftime("%d-%m-%Y")
    return coingecko_close(symbol, day), f"https://api.coingecko.com/api/v3/coins/{COINS[symbol]}/history?date={snap}"


def judge(r, price_on) -> tuple[int, float, str]:
    """算一条价格类预测的结果。price_on(symbol, day) -> (价格, 来源)。返回 (结果, 结算值, 来源)。"""
    day = pd.to_datetime(r["结算日期"]).date()
    px, src = price_on(r["币种"], day)
    kind = r["类型"]
    if kind == "above":
        return int(px > float(r["阈值"])), px, src
    if kind == "below":
        return int(px < float(r["阈值"])), px, src
    if kind == "between":
        return int(float(r["阈值"]) <= px <= float(r["阈值上限"])), px, src
    if kind == "up":
        ref = pd.to_datetime(r["参考日期"]).date()
        ref_px, ref_src = price_on(r["币种"], ref)
        return int(px > ref_px), px, f"{src}；对比 {ref} 收盘 {ref_px:,.2f}：{ref_src}"
    raise ValueError(f"不认识的类型 {kind}")


def cmd_settle(a):
    df = load()
    if a.id is not None:
        m = df["id"] == a.id
        if not m.any():
            raise SystemExit(f"没有 #{a.id}")
        if a.result not in (0, 1):
            raise SystemExit("人工结算要给 --result 1 或 0")
        i = df.index[m][0]
        df.loc[i, ["结果", "结算值", "结算来源", "Brier", "状态"]] = [
            a.result, a.value, a.source, brier(float(df.loc[i, "概率"]), a.result), DONE]
        save(df)
        print(f"#{a.id} 已结算：结果 {a.result}，Brier {df.loc[i, 'Brier']}")
        return

    today_utc = datetime.now(timezone.utc).date()
    n = 0
    for i, r in df[df["状态"] == PENDING].iterrows():
        settle_day = pd.to_datetime(r["结算日期"]).date()
        if today_utc <= settle_day:  # 收盘价要等次日 00:00 UTC 才有
            continue
        if r["类型"] not in PRICE_KINDS:
            print(f"#{r['id']} 到期了，需要人工结算：{r['问题']}")
            continue
        try:
            out, px, src = judge(r, close_price)
        except Exception as e:
            print(f"#{r['id']} 拉价格失败，下次再试：{e}")
            continue
        df.loc[i, ["结果", "结算值", "结算来源", "Brier", "状态"]] = [
            out, px, src, brier(float(r["概率"]), out), DONE]
        n += 1
        print(f"#{r['id']} {r['问题']} → 收盘 {px:,.2f}，结果 {out}，Brier {df.loc[i, 'Brier']}")
    save(df)
    print(f"自动结算 {n} 条")


def cmd_review(a):
    df = load()
    end = date.fromisoformat(a.date)
    start = end - timedelta(days=6)
    done = df[df["状态"] == DONE].copy()
    done["_d"] = pd.to_datetime(done["结算日期"]).dt.date
    week = done[(done["_d"] >= start) & (done["_d"] <= end)]
    if week.empty:
        raise SystemExit(f"{start} 到 {end} 没有已结算的预测，先跑 settle")

    rows = []
    for _, r in week.iterrows():
        b = float(r["Brier"])
        rows.append([
            cell(f"#{r['id']}", align="c"), cell(r["问题"]),
            cell(f"{float(r['概率']):.0%}", align="r"),
            cell("发生" if int(r["结果"]) == 1 else "没发生", align="c"),
            cell(f"{b:.3f}", "up" if b < BASELINE else ("down" if b > BASELINE else None), "r"),
        ])
    wk = week["Brier"].astype(float).mean()
    allb = done["Brier"].astype(float).mean()
    sub = (f"{start} ~ {end}｜本周平均 Brier {wk:.3f}｜累计 {allb:.3f}（{len(done)} 条）"
           f"｜全猜 50% = {BASELINE}，越低越准")
    p = render_table(OUTPUT / a.date / "预测复盘.png", "本周预测复盘",
                     ["编号", "预测", "概率", "结果", "Brier"], rows,
                     source="Yahoo Finance / CoinGecko / Farside，各题结算来源见 data/predictions.xlsx", subtitle=sub,
                     col_widths=[100, 560, 130, 150, 150])
    print(f"复盘图：{p}")
    print(sub)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--q", required=True, help="预测内容")
    s.add_argument("--p", type=float, required=True, help="概率 0~1")
    s.add_argument("--settle", required=True, help="结算日期 YYYY-MM-DD")
    s.add_argument("--kind", choices=["above", "below", "between", "up", "manual"])
    s.add_argument("--symbol")
    s.add_argument("--threshold", type=float, help="above/below 的阈值，between 的下限")
    s.add_argument("--high", type=float, help="between 的上限")
    s.add_argument("--ref", help="up：拿哪天的收盘比，YYYY-MM-DD")
    s.add_argument("--date", default=date.today().isoformat(), help="发布日期")
    s = sub.add_parser("settle")
    s.add_argument("--id", type=int)
    s.add_argument("--result", type=int)
    s.add_argument("--value")
    s.add_argument("--source")
    s = sub.add_parser("review")
    s.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args()
    {"add": cmd_add, "settle": cmd_settle, "review": cmd_review}[a.cmd](a)


if __name__ == "__main__":
    main()
