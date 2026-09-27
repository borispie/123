"""一条命令拉当天数据，存到 data/YYYY-MM-DD.csv。

    python scripts/fetch_daily.py            # 今天
    python scripts/fetch_daily.py --date 2026-09-27

拉的东西：
  1. BTC/ETH/SOL/BNB/HYPE 价格、24h/7天/30天涨跌、市值、FDV   <- CoinGecko
  2. BTC、ETH 现货 ETF 最近一个交易日的净流入（百万美元）        <- Farside
  3. 未来 7 天解锁                                           <- data/unlocks.csv（从 Tokenomist 抄）
  4. 协议手续费 / 收入 / 持币人收入（24h、7天、30天）          <- DefiLlama（common.DEFILLAMA_PROTOCOLS）
  5. 稳定币总市值、DeFi 总 TVL 和 7 天变化                     <- DefiLlama
  6. 美债 2/5/10 年收益率、联邦基金利率上限和一周变化          <- FRED（要 FRED_API_KEY）
  7. 预测市场概率                                           <- Polymarket（data/polymarket.csv 里列要跟踪的市场）

拉不到的数据不会编，value 留空，note 写【需补充：xxx】。
Farside 从云服务器访问会被 Cloudflare 挡（403）。拉不到时会去读 data/etf_manual.csv（手填的备用表），
每行：date,symbol,net_flow_usd_m,source_url，取不晚于当天的最近一个交易日。
CSV 是长表：每行一个数字，带来源链接，方便写帖子时说出出处。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import os
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import pandas as pd

from common import (COINS, DATA, DEFILLAMA_PROTOCOLS, FRED_SERIES, UA, coingecko_headers, get, launch_chromium,
                    missing, now_utc)

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
            b = launch_chromium(p)
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


# ---------- 4/5. DefiLlama ----------

LLAMA = "https://api.llama.fi"
LLAMA_STABLE = "https://stablecoins.llama.fi/stablecoincharts/all"
FEE_TYPES = (("dailyFees", "fees"), ("dailyRevenue", "revenue"), ("dailyHoldersRevenue", "holders_revenue"))


def fees_ref_date(d: dict) -> str:
    """total24h 是最后一个完整的 UTC 日（不是今天），日期取 totalDataChart 最后一个点。"""
    chart = d.get("totalDataChart") or []
    if not chart:
        return ""
    return datetime.fromtimestamp(int(chart[-1][0]), timezone.utc).date().isoformat()


def fetch_protocols() -> list[dict]:
    """每个协议的手续费、收入、持币人收入（Hyperliquid 的持币人收入基本就是回购）。"""
    out = []
    for sym, slug in DEFILLAMA_PROTOCOLS.items():
        page = f"https://defillama.com/protocol/{slug}"
        for dtype, name in FEE_TYPES:
            try:
                d = get(f"{LLAMA}/summary/fees/{slug}",
                        params={"dataType": dtype, "excludeTotalDataChartBreakdown": "true"}).json()
            except Exception as e:
                print(f"[DefiLlama] {slug} {dtype} 拉取失败：{e}", file=sys.stderr)
                d = {}
            ref = fees_ref_date(d)
            for k in ("24h", "7d", "30d"):
                v = d.get(f"total{k}")
                out.append(row("defi", sym, f"{name}_{k}", v, "USD", "DefiLlama", page, ref_date=ref,
                               note="" if v is not None else missing(f"{sym} {name} {k}")))
    return out


def _usd(x) -> float | None:
    """DefiLlama 稳定币的金额有时是 {peggedUSD: .., peggedEUR: ..}，加总成美元。"""
    if isinstance(x, dict):
        vals = [float(v) for v in x.values() if isinstance(v, (int, float))]
        return sum(vals) if vals else None
    return float(x) if isinstance(x, (int, float)) else None


def latest_and_week_ago(points: list[tuple[int, float]]) -> tuple[str, float, float | None] | None:
    """points = [(unix 秒, 数值)]。返回 (最新日期, 最新值, 7 天变化 %)。"""
    pts = sorted((t, v) for t, v in points if v is not None)
    if not pts:
        return None
    t1, v1 = pts[-1]
    older = [v for t, v in pts if t <= t1 - 7 * 86400]
    chg = (v1 / older[-1] - 1) * 100 if older and older[-1] else None
    return datetime.fromtimestamp(t1, timezone.utc).date().isoformat(), v1, chg


def parse_stablecoins(data) -> tuple[str, float, float | None] | None:
    return latest_and_week_ago([(int(p["date"]), _usd(p.get("totalCirculatingUSD"))) for p in data])


def parse_tvl(data) -> tuple[str, float, float | None] | None:
    return latest_and_week_ago([(int(p["date"]), _usd(p.get("tvl"))) for p in data])


def fetch_defi_totals() -> list[dict]:
    out = []
    jobs = (("stablecoin", LLAMA_STABLE, "https://defillama.com/stablecoins", parse_stablecoins, "稳定币总市值"),
            ("defi_tvl", f"{LLAMA}/v2/historicalChainTvl", "https://defillama.com/", parse_tvl, "DeFi 总 TVL"))
    for name, url, page, parse, label in jobs:
        try:
            res = parse(get(url).json())
            if res is None:
                raise ValueError("没有数据")
            d, v, chg = res
            out.append(row("defi", "ALL", name, v, "USD", "DefiLlama", page, ref_date=d))
            out.append(row("defi", "ALL", f"{name}_chg_7d", chg, "%", "DefiLlama", page, ref_date=d,
                           note="" if chg is not None else missing(f"{label} 7 天变化")))
        except Exception as e:
            print(f"[DefiLlama] {label} 拉取失败：{e}", file=sys.stderr)
            out.append(row("defi", "ALL", name, None, "USD", "DefiLlama", page, note=missing(label)))
    return out


# ---------- 6. FRED ----------

FRED = "https://api.stlouisfed.org/fred/series/observations"


def parse_fred(obs: list[dict]) -> tuple[str, float, float | None] | None:
    """FRED 缺值写成 "."。返回 (最新日期, 最新值, 和 7 天前比的变化，单位百分点)。"""
    pts = []
    for o in obs:
        try:
            pts.append((date.fromisoformat(o["date"]), float(o["value"])))
        except (ValueError, KeyError):
            continue
    if not pts:
        return None
    pts.sort()
    d1, v1 = pts[-1]
    older = [v for d, v in pts if d <= d1 - timedelta(days=7)]
    return d1.isoformat(), v1, (round(v1 - older[-1], 4) if older else None)


def fetch_macro(day: date) -> list[dict]:
    key = os.environ.get("FRED_API_KEY")
    out = []
    for name, sid in FRED_SERIES.items():
        page = f"https://fred.stlouisfed.org/series/{sid}"
        if not key:
            out.append(row("macro", name, "value", None, "%", "FRED", page,
                           note=missing(f"{sid}：先设环境变量 FRED_API_KEY（fred.stlouisfed.org 免费申请）")))
            continue
        try:
            obs = get(FRED, params={"series_id": sid, "api_key": key, "file_type": "json",
                                    "observation_start": (day - timedelta(days=30)).isoformat()}).json()["observations"]
            res = parse_fred(obs)
            if res is None:
                raise ValueError("没有数据")
            d, v, chg = res
            out.append(row("macro", name, "value", v, "%", "FRED", page, ref_date=d))
            out.append(row("macro", name, "chg_1w", chg, "pp", "FRED", page, ref_date=d,
                           note="" if chg is not None else missing(f"{sid} 一周变化")))
        except Exception as e:
            print(f"[FRED] {sid} 拉取失败：{e}", file=sys.stderr)
            out.append(row("macro", name, "value", None, "%", "FRED", page, note=missing(f"{sid}")))
    return out


# ---------- 7. Polymarket ----------

GAMMA = "https://gamma-api.polymarket.com/markets/slug/{slug}"
GAMMA_EVENT = "https://gamma-api.polymarket.com/events/slug/{slug}"
PM_MAX_PER_EVENT = 8
PM_FILE = DATA / "polymarket.csv"
PM_COLS = ["slug", "label"]


def parse_polymarket(m: dict) -> tuple[float, str]:
    """返回 (Yes 的概率 0~1, 结束日期)。outcomes / outcomePrices 是 JSON 字符串。"""
    outcomes = m.get("outcomes")
    prices = m.get("outcomePrices")
    outcomes = json.loads(outcomes) if isinstance(outcomes, str) else (outcomes or [])
    prices = json.loads(prices) if isinstance(prices, str) else (prices or [])
    if not prices:
        raise ValueError("没有 outcomePrices")
    names = [str(o).lower() for o in outcomes]
    i = names.index("yes") if "yes" in names else 0
    return float(prices[i]), (m.get("endDate") or "")[:10]


PM_WEB = "https://polymarket.com/event/{slug}"


def pm_page(m: dict, fallback_slug: str) -> str:
    """帖子回复里放的来源链接：polymarket.com 的事件页，不放 API 地址。"""
    evs = m.get("events") or []
    return PM_WEB.format(slug=(evs[0].get("slug") if evs else None) or fallback_slug)


def pick_event_markets(markets: list[dict], n: int = PM_MAX_PER_EVENT) -> list[dict]:
    """事件里进行中的市场，按成交量取前 n 个，再按价位（groupItemThreshold）排好。"""
    live = [m for m in markets if not m.get("closed")]
    top = sorted(live, key=lambda m: float(m.get("volumeNum") or m.get("volume") or 0), reverse=True)[:n]
    return sorted(top, key=lambda m: float(m.get("groupItemThreshold") or 0))


def fetch_polymarket() -> list[dict]:
    """data/polymarket.csv 每行一个：slug（网址 polymarket.com/event/xxx 或 /market/xxx 里的 xxx）, label（帖子里怎么叫它）。
    先按「单个市场」查，查不到再按「事件」查；一个事件里有好几个市场（比如不同价位），每个都记一行。"""
    if not PM_FILE.exists():
        PM_FILE.write_text(",".join(PM_COLS) + "\n", encoding="utf-8")
    df = pd.read_csv(PM_FILE, dtype=str).fillna("")
    out = []
    for _, r in df.iterrows():
        slug = r["slug"].strip()
        if not slug:
            continue
        label = r["label"].strip() or slug
        url = GAMMA.format(slug=slug)
        try:
            m = get(url, tries=1).json()
            p, end = parse_polymarket(m)
            out.append(row("polymarket", label, "yes_prob", round(p * 100, 1), "%", "Polymarket",
                           pm_page(m, slug), ref_date=end))
            continue
        except Exception:
            pass
        ev_url = GAMMA_EVENT.format(slug=slug)
        try:
            ev = get(ev_url).json()
            markets = pick_event_markets(ev.get("markets", []))
            if not markets:
                raise ValueError("事件里没有进行中的市场")
            for m in markets:
                p, end = parse_polymarket(m)
                name = m.get("groupItemTitle") or m.get("question") or ""
                out.append(row("polymarket", f"{label} {name}".strip(), "yes_prob", round(p * 100, 1), "%",
                               "Polymarket", PM_WEB.format(slug=ev.get("slug") or slug), ref_date=end))
        except Exception as e:
            print(f"[Polymarket] {slug} 拉取失败：{e}", file=sys.stderr)
            out.append(row("polymarket", label, "yes_prob", None, "%", "Polymarket", PM_WEB.format(slug=slug),
                           note=missing(f"Polymarket {label} 概率（检查 data/polymarket.csv 里的 slug）")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    day = date.fromisoformat(args.date)

    rows = (fetch_prices() + fetch_etf(day) + fetch_unlocks(day) + fetch_protocols()
            + fetch_defi_totals() + fetch_macro(day) + fetch_polymarket())
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
