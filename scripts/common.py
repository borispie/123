"""公共配置和工具：路径、币种、数字格式、网络请求、Excel 风格出图。"""
from __future__ import annotations

import html
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
TEMPLATES = ROOT / "templates"

# 符号 -> CoinGecko id
COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "HYPE": "hyperliquid",
}
# 符号 -> DefiLlama 协议 slug（拉手续费、收入、持币人收入）
DEFILLAMA_PROTOCOLS = {
    "HYPE": "hyperliquid",
}
# 名字 -> FRED 数据代码（美债收益率、利率），要环境变量 FRED_API_KEY
FRED_SERIES = {
    "us2y": "DGS2",        # 2 年期美债收益率
    "us5y": "DGS5",        # 5 年期
    "us10y": "DGS10",      # 10 年期
    "fed_upper": "DFEDTARU",  # 联邦基金利率目标上限
}
# 我持有的币（写帖子时自动加「（我持有）」）
HOLDINGS = {"BTC", "HYPE"}

DISCLAIMER = "不构成投资建议"
MINUS = "−"  # 图里用的减号 U+2212

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def today_str() -> str:
    return date.today().isoformat()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def missing(what: str) -> str:
    return f"【需补充：{what}】"


def get(url: str, params: dict | None = None, headers: dict | None = None,
        tries: int = 3, timeout: int = 20) -> requests.Response:
    """带重试的 GET。失败抛异常，由调用方决定写【需补充】。"""
    h = {"User-Agent": UA}
    h.update(headers or {})
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 429:  # 限流，等一下
                time.sleep(5 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"请求失败 {url}: {last}")


def coingecko_headers() -> dict:
    key = os.environ.get("COINGECKO_API_KEY")
    return {"x-cg-demo-api-key": key} if key else {}


# ---------- 数字格式 ----------

def fmt_pct(x, minus: str = MINUS, digits: int = 2) -> str:
    if x is None or x != x:  # None 或 NaN
        return "—"
    sign = "+" if x > 0 else (minus if x < 0 else "")
    return f"{sign}{abs(x):.{digits}f}%"


def fmt_signed(x, minus: str = MINUS, digits: int = 1, unit: str = "") -> str:
    if x is None or x != x:
        return "—"
    sign = "+" if x > 0 else (minus if x < 0 else "")
    return f"{sign}{abs(x):,.{digits}f}{unit}"


def fmt_price(x) -> str:
    if x is None or x != x:
        return "—"
    if x >= 1000:
        return f"${x:,.0f}"
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def fmt_big(x) -> str:
    """市值、FDV 这种大数：$1.23T / $45.6B / $789M"""
    if x is None or x != x:
        return "—"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(x) >= div:
            return f"${x / div:,.2f}{suf}"
    return f"${x:,.0f}"


def trend(x) -> str | None:
    if x is None or x != x or x == 0:
        return None
    return "up" if x > 0 else "down"


# ---------- Excel 风格出图 ----------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", sans-serif; }
#root { width: 1200px; background: #fff; padding: 28px 28px 20px; }
h1 { font-size: 30px; font-weight: 700; color: #1a1a1a; margin-bottom: 6px; }
.sub { font-size: 17px; color: #666; margin-bottom: 16px; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; font-size: 21px; }
td, th { border: 1px solid #d4d4d4; height: 46px; padding: 0 12px; white-space: nowrap;
         overflow: hidden; text-overflow: ellipsis; }
.colhdr td { background: #f3f3f3; color: #555; text-align: center; font-size: 15px; height: 26px; }
.rownum { background: #f3f3f3; color: #555; text-align: center; font-size: 15px; width: 46px; padding: 0; }
.head { background: #1F4E78; color: #fff; font-weight: 700; text-align: center; }
.up { background: #C6EFCE; color: #006100; }
.down { background: #FFC7CE; color: #9C0006; }
.r { text-align: right; font-variant-numeric: tabular-nums; }
.c { text-align: center; }
.b { font-weight: 700; }
.foot { margin-top: 14px; font-size: 16px; color: #666; display: flex; justify-content: space-between; }
"""

MAX_H = 1500


def cell(text, kind: str | None = None, align: str = "l", bold: bool = False) -> dict:
    return {"text": str(text), "kind": kind, "align": align, "bold": bold}


def pct_cell(x) -> dict:
    return cell(fmt_pct(x), trend(x), "r")


def _col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def table_html(title: str, headers: list[str], rows: list[list[dict]], source: str,
               subtitle: str = "", col_widths: list[int] | None = None) -> str:
    n = len(headers)
    esc = html.escape
    cols = '<col style="width:46px">' + "".join(
        f'<col style="width:{w}px">' if col_widths else "<col>" for w in (col_widths or [0] * n))
    out = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div id='root'>",
           f"<h1>{esc(title)}</h1>"]
    if subtitle:
        out.append(f"<div class='sub'>{esc(subtitle)}</div>")
    out.append(f"<table><colgroup>{cols}</colgroup>")
    out.append("<tr class='colhdr'><td></td>" + "".join(f"<td>{_col_letter(i)}</td>" for i in range(n)) + "</tr>")
    out.append("<tr><td class='rownum'>1</td>" + "".join(f"<td class='head'>{esc(h)}</td>" for h in headers) + "</tr>")
    for ri, row in enumerate(rows, start=2):
        tds = []
        for c in row:
            cls = [c["kind"] or "", {"r": "r", "c": "c"}.get(c["align"], ""), "b" if c["bold"] else ""]
            tds.append(f"<td class='{' '.join(x for x in cls if x)}'>{esc(c['text'])}</td>")
        out.append(f"<tr><td class='rownum'>{ri}</td>{''.join(tds)}</tr>")
    out.append("</table>")
    out.append(f"<div class='foot'><span>数据来源：{esc(source)}</span><span>{DISCLAIMER}</span></div>")
    out.append("</div></body></html>")
    return "".join(out)


# 云端容器预装的浏览器。pip 把 Playwright 升级后版本对不上时，用它兜底。
PREINSTALLED_CHROMIUM = ("/opt/pw-browsers/chromium",)


def launch_chromium(p):
    """先用 CHROMIUM_PATH；没设就用 Playwright 自带的；自带的启动失败（版本对不上）再试预装的。"""
    exe = os.environ.get("CHROMIUM_PATH")
    if exe:
        return p.chromium.launch(executable_path=exe)
    try:
        return p.chromium.launch()
    except Exception as e:
        for path in PREINSTALLED_CHROMIUM:
            if Path(path).exists():
                print(f"Playwright 自带浏览器启动失败，改用 {path}")
                return p.chromium.launch(executable_path=path)
        raise RuntimeError(f"浏览器启动失败：{e}\n在 Mac 上跑一次 playwright install chromium 就好") from e


def render_png(page_html: str, out_path: Path) -> Path:
    """HTML -> PNG，宽 1200，2 倍分辨率，高度超过 1500 会报错提醒拆图。"""
    from playwright.sync_api import sync_playwright

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
        page.set_content(page_html)
        page.evaluate("document.fonts.ready")
        el = page.locator("#root")
        h = el.bounding_box()["height"]
        if h > MAX_H:
            browser.close()
            raise ValueError(f"图高 {h:.0f}px 超过 {MAX_H}px，手机上会被裁，请减少行数或拆成两张")
        el.screenshot(path=str(out_path))
        browser.close()
    return out_path


def render_table(out_path: Path, title: str, headers: list[str], rows: list[list[dict]],
                 source: str, subtitle: str = "", col_widths: list[int] | None = None) -> Path:
    return render_png(table_html(title, headers, rows, source, subtitle, col_widths), out_path)


# ---------- 读每日 CSV ----------

class Daily:
    """data/YYYY-MM-DD.csv 的读取器。v() 拿数字，拿不到返回 None。"""

    def __init__(self, day: str):
        import pandas as pd
        self.day = day
        self.path = DATA / f"{day}.csv"
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} 不存在，先跑 python scripts/fetch_daily.py --date {day}")
        self.df = pd.read_csv(self.path, dtype=str, encoding="utf-8-sig").fillna("")

    def _row(self, section, symbol, metric):
        m = self.df[(self.df.section == section) & (self.df.symbol == symbol) & (self.df.metric == metric)]
        return None if m.empty else m.iloc[0]

    def v(self, section, symbol, metric) -> float | None:
        r = self._row(section, symbol, metric)
        if r is None or r["value"] == "":
            return None
        try:
            return float(r["value"])
        except ValueError:
            return None

    def ref_date(self, section, symbol, metric) -> str:
        r = self._row(section, symbol, metric)
        return "" if r is None else r["ref_date"]

    def rows(self, section):
        return self.df[self.df.section == section]

    def sources(self, section=None) -> dict[str, str]:
        """{链接: 来源名}，按链接去重，写回复里的来源用。"""
        df = self.df if section is None else self.rows(section)
        out = {}
        for _, r in df.iterrows():
            if r["value"] != "" and r["source_url"]:
                out.setdefault(r["source_url"], r["source"])
        return out
