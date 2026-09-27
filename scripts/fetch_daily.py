"""一条命令拉当天数据，存到 data/YYYY-MM-DD.csv。

    python scripts/fetch_daily.py            # 今天
    python scripts/fetch_daily.py --date 2026-09-27

拉的东西：
  1. BTC/ETH/SOL/BNB/HYPE 价格、24h/7天/30天涨跌、市值、FDV   <- CoinGecko
  2. BTC、ETH 现货 ETF 最近一个交易日的净流入（百万美元）        <- Farside
  3. 未来 7 天解锁                                           <- data/unlocks.csv（从 Tokenomist 抄）

拉不到的数据不会编，value 留空，note 写【需补充：xxx】。
Farside 从云服务器访问会被 Cloudflare 挡（403）。拉不到时会去读 data/etf_manual.csv（手填的备用表），
每行：date,symbol,net_flow_usd_m,source_url，取不晚于当天的最近一个交易日。
CSV 是长表：每行一个数字，带来源链接，方便写帖子时说出出处。
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import os
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

import pandas as pd

from common import COINS, DATA, UA, coingecko_headers, get, missing, now_utc

FIELDS = ["section", "symbol", "metric", "value", "unit", "ref_date", "source", "source_url", "note", "fetched_at"]

CG_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
FARSIDE = {
    "BTC": "https://farside.co.uk/bitcoin-etf-flow-all-data/",
    "ETH": "https://farside.co.uk/ethereum-etf-flow-all-data/",
}
TOKENOMIST_URL = "https://tokenomist.ai/"
# CoinGecko 网页地址和 API id 不完全一样（BNB 的 API id 是 binancecoin，网页是 binance-coin）
CG_WEB_SLUG = {"binancecoin": "binance-coin"}


def row(section, symbol, metric, value, unit, source, source_url, ref_date="", note=""):
    return {"section": section, "symbol": symbol, "metric": metric,
            "value": "" if value is None else value, "unit": unit, "ref_date": ref_date,
            "source": source, "source_url": source_url, "note": note, "fetched_at": now_utc()}


# ---------- 1. 价格 ----------

PRICE_METRICS = [
    ("price", "current_price", "USD"),
    ("chg_24h", "price_change_percentage_24h_in_currency", "%"),
    ("chg_7d", "price_change_percentage_7d_in_currency", "%"),
    ("chg_30d", "price_change_percentage_30d_in_currency", "%"),
    ("market_cap", "market_cap", "USD"),
    ("fdv", "fully_diluted_valuation", "USD"),
]


def fetch_prices() -> list[dict]:
    ids = ",".join(COINS.values())
    params = {"vs_currency": "usd", "ids": ids, "price_change_percentage": "24h,7d,30d"}
    url = f"{CG_MARKETS}?vs_currency=usd&ids={ids}&price_change_percentage=24h,7d,30d"
    try:
        data = get(CG_MARKETS, params=params, headers=coingecko_headers()).json()
    except Exception as e:
        print(f"[价格] CoinGecko 拉取失败：{e}", file=sys.stderr)
        return [row("price", s, m, None, u, "CoinGecko", url, note=missing(f"{s} {m}"))
                for s in COINS for m, _, u in PRICE_METRICS]
    by_id = {d["id"]: d for d in data}
    out = []
    for sym, cid in COINS.items():
        d = by_id.get(cid, {})
        page = f"https://www.coingecko.com/en/coins/{CG_WEB_SLUG.get(cid, cid)}"
        for metric, key, unit in PRICE_METRICS:
            v = d.get(key)
            out.append(row("price", sym, metric, v, unit, "CoinGecko", page,
                           ref_date=(d.get("last_updated") or "")[:10],
                           note="" if v is not None else missing(f"{sym} {metric}")))
    return out


# ---------- 2. ETF 流入 ----------

def _num(s) -> float | None:
    """Farside 的格式：'123.4'、'(56.7)' 表示负数、'-' 表示 0 / 没数据。"""
    s = str(s).strip().replace(",", "")
    if s in ("", "-", "nan", "NaN"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def parse_farside(page_html: str) -> tuple[str, float] | None:
    """返回 (日期 YYYY-MM-DD, 总净流入 百万美元)，取最后一个有数的交易日。"""
    tables = pd.read_html(io.StringIO(page_html))
    for t in tables:
        t = t.astype(str)
        last = None
        for _, r in t.iterrows():
            first = r.iloc[0].strip()
            m = re.match(r"^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$", first)
            if not m:
                continue
            total = _num(r.iloc[-1])
            if total is None:
                continue
            d = pd.to_datetime(first, format="%d %b %Y").date().isoformat()
            last = (d, total)
        if last:
            return last
    return None


def _fetch_html(url: str) -> str:
    try:
        return get(url).text
    except Exception:
        # Farside 有时挡脚本，用浏览器再试一次
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = os.environ.get("CHROMIUM_PATH")
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            pg = b.new_page(user_agent=UA)
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_selector("table", timeout=30000)
            h = pg.content()
            b.close()
            return h


ETF_MANUAL = DATA / "etf_manual.csv"
ETF_MANUAL_COLS = ["date", "symbol", "net_flow_usd_m", "source_url"]


def manual_etf(sym: str, day: date) -> tuple[str, float, str] | None:
    """从 data/etf_manual.csv 找 sym 在 day 当天或之前最近的一条：(日期, 净流入, 来源链接)。"""
    if not ETF_MANUAL.exists():
        ETF_MANUAL.write_text(",".join(ETF_MANUAL_COLS) + "\n", encoding="utf-8")
        return None
    df = pd.read_csv(ETF_MANUAL, dtype=str).fillna("")
    best = None
    for _, r in df.iterrows():
        try:
            d = date.fromisoformat(r["date"].strip())
            v = float(r["net_flow_usd_m"])
        except ValueError:
            continue
        if r["symbol"].strip().upper() == sym and d <= day and (best is None or d > best[0]):
            best = (d, v, r["source_url"].strip() or FARSIDE[sym])
    return None if best is None else (best[0].isoformat(), best[1], best[2])


def fetch_etf(day: date | None = None) -> list[dict]:
    day = day or date.today()
    out = []
    for sym, url in FARSIDE.items():
        try:
            res = parse_farside(_fetch_html(url))
            if res is None:
                raise ValueError("页面里没找到数据表")
            d, total = res
            out.append(row("etf", sym, "etf_net_flow", total, "USD m", "Farside", url, ref_date=d))
        except Exception as e:
            print(f"[ETF] {sym} 拉取失败：{e}", file=sys.stderr)
            m = manual_etf(sym, day)
            if m:
                d, total, src = m
                print(f"[ETF] {sym} 改用手填表 data/etf_manual.csv：{d} {total}", file=sys.stderr)
                out.append(row("etf", sym, "etf_net_flow", total, "USD m", "Farside（手填）", src, ref_date=d))
            else:
                out.append(row("etf", sym, "etf_net_flow", None, "USD m", "Farside", url,
                               note=missing(f"{sym} ETF 净流入，可以填到 data/etf_manual.csv")))
    return out


# ---------- 3. 解锁 ----------

UNLOCK_FILE = DATA / "unlocks.csv"
UNLOCK_COLS = ["date", "symbol", "amount", "pct_circulating", "value_usd", "source_url"]


def fetch_unlocks(day: date) -> list[dict]:
    """Tokenomist 的 API 要付费 key，所以先用手填表：data/unlocks.csv。
    每周看一次 tokenomist.ai，把下周的解锁抄进去（一行一个）。"""
    if not UNLOCK_FILE.exists():
        UNLOCK_FILE.write_text(",".join(UNLOCK_COLS) + "\n", encoding="utf-8")
    df = pd.read_csv(UNLOCK_FILE, dtype=str).fillna("")
    end = day + timedelta(days=7)
    out = []
    for _, r in df.iterrows():
        try:
            d = date.fromisoformat(r["date"].strip())
        except ValueError:
            continue
        if day < d <= end:
            src = r["source_url"] or TOKENOMIST_URL
            src_name = "Tokenomist" if "tokenomist" in src else urlparse(src).netloc.removeprefix("www.")
            for metric, unit in (("amount", "token"), ("pct_circulating", "%"), ("value_usd", "USD")):
                v = r[metric].strip()
                out.append(row("unlock", r["symbol"].strip().upper(), metric, v or None, unit,
                               src_name, src, ref_date=d.isoformat(),
                               note="" if v else missing(f"{r['symbol']} 解锁 {metric}")))
    if not out:
        out.append(row("unlock", "", "none", None, "", "Tokenomist", TOKENOMIST_URL,
                       note=missing(f"{day + timedelta(days=1)} 到 {end} 的解锁，填到 data/unlocks.csv")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    day = date.fromisoformat(args.date)

    rows = fetch_prices() + fetch_etf(day) + fetch_unlocks(day)
    DATA.mkdir(exist_ok=True)
    path = DATA / f"{day.isoformat()}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig：Excel 打开不乱码
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    todo = [r["note"] for r in rows if r["note"]]
    print(f"已保存 {path}（{len(rows)} 行）")
    if todo:
        print(f"有 {len(todo)} 项需补充：")
        for t in dict.fromkeys(todo):
            print("  ", t)


if __name__ == "__main__":
    main()
