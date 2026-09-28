"""按当天栏目生成发布包：主贴、回复、短推、一键发帖链接 + 规则检查。

    python scripts/make_post_pack.py                    # 今天
    python scripts/make_post_pack.py --date 2026-09-28
    python scripts/make_post_pack.py --column 周二代币经济   # 不按星期，指定栏目

输出 output/日期/发布包.md（自己看）和 发布包.json（post_to_x.py 读这个发推）。
数字只从 data/日期.csv 和 data/predictions.xlsx 来，没有的一律是【需补充：xxx】。
最后会列出违反 CLAUDE.md 发帖规则的地方。
"""
from __future__ import annotations

import argparse
import json
import re
import string
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd

from common import (COINS, DATA as DATA_DIR, DEFILLAMA_PROTOCOLS, DISCLAIMER, FRED_SERIES, HOLDINGS, OUTPUT, ROOT, TEMPLATES, Daily,
                    fmt_big, fmt_pct, fmt_price, fmt_signed, missing)

COLUMNS = ["周一数据", "周二代币经济", "周三链上巨鲸", "周四宏观", "周五项目深度", "周六统计小课", "周日预测复盘"]
BANNED = ["必涨", "必跌", "稳了"]

# 每个栏目用到哪几块数据：回复里只写这些来源的名字
COLUMN_SECTIONS = {
    "周一数据": ["price", "etf", "defi"],
    "周二代币经济": ["unlock", "price", "defi"],
    "周三链上巨鲸": ["etf", "price"],
    "周四宏观": ["macro", "etf", "price"],
    "周五项目深度": ["defi", "price"],
    "周六统计小课": ["price"],
    "周日预测复盘": ["polymarket"],
}
# 每个栏目主贴带哪几张图（按顺序，最多 4 张，没生成的跳过）
COLUMN_IMAGES = {
    "周一数据": ["rank_7d", "fdv", "etf"],
    "周二代币经济": ["unlock", "fdv"],
    "周三链上巨鲸": ["etf", "rank_7d"],
    "周四宏观": ["etf", "price"],
    "周五项目深度": ["fdv", "price"],
    "周六统计小课": ["rank_7d"],
    "周日预测复盘": ["预测复盘", "price"],
}
VIEWS = DATA_DIR / "views.csv"  # 想用自己的看法：一行 date,view
MAX_TAGS = 2
MINUS = "-"  # 帖子里用普通减号，方便复制


def tag(sym: str) -> str:
    return f"${sym}（我持有）" if sym in HOLDINGS else f"${sym}"


# ---------- 变量 ----------

def price_vars(d: Daily | None) -> dict:
    v = {}
    for s in COINS:
        v[f"{s}_tag"] = tag(s)
        if d is None:
            continue
        get = lambda m: d.v("price", s, m)
        if get("price") is not None:
            v[f"{s}_price"] = fmt_price(get("price"))
        for m, key in (("chg_24h", "24h"), ("chg_7d", "7d"), ("chg_30d", "30d")):
            if get(m) is not None:
                v[f"{s}_{key}"] = fmt_pct(get(m), MINUS)
    if d is None:
        return v
    ch7 = {s: d.v("price", s, "chg_7d") for s in COINS}
    ch7 = {s: x for s, x in ch7.items() if x is not None}
    if len(ch7) >= 2:
        best, worst = max(ch7, key=ch7.get), min(ch7, key=ch7.get)
        v.update(best_7d=best, best_7d_tag=tag(best), best_7d_pct=fmt_pct(ch7[best], MINUS),
                 worst_7d=worst, worst_7d_tag=tag(worst), worst_7d_pct=fmt_pct(ch7[worst], MINUS))
    share = {s: d.v("price", s, "market_cap") / d.v("price", s, "fdv") for s in COINS
             if d.v("price", s, "market_cap") and d.v("price", s, "fdv")}
    if share:
        s_min = min(share, key=share.get)
        r = min(share[s_min], 1.0)
        v["fdv_line"] = f"{tag(s_min)} 的流通市值只占 FDV 的 {r * 100:.0f}%，还有 {(1 - r) * 100:.0f}% 的币没放出来。"
    for s in ("BTC", "ETH"):
        x = d.v("etf", s, "etf_net_flow")
        if x is not None:
            v[f"etf_{s}"] = fmt_signed(x, MINUS)
    etf_d = d.ref_date("etf", "BTC", "etf_net_flow")
    if etf_d:
        v["etf_date"] = etf_d

    u = d.rows("unlock")
    u = u[u.metric != "none"]
    if not u.empty:
        lines, short = [], []
        for (day, sym), g in u.groupby(["ref_date", "symbol"], sort=True):
            val = {r["metric"]: r["value"] for _, r in g.iterrows()}
            amt = f"{float(val['amount']):,.0f} 枚" if val.get("amount") else missing(f"{sym} 解锁数量")
            pct = f"占流通 {float(val['pct_circulating']):.2f}%" if val.get("pct_circulating") else missing(f"{sym} 占流通比例")
            usd = f"约 {fmt_big(float(val['value_usd']))}" if val.get("value_usd") else missing(f"{sym} 解锁价值")
            lines.append(f"- {day[5:]} {tag(sym)} {amt}（{pct}，{usd}）")
            short.append(f"{tag(sym)} {day[5:]}")
        v["unlock_list"] = "\n".join(lines)
        v["unlock_list_short"] = "、".join(short)
    return v


def data_vars(d: Daily | None) -> dict:
    """DefiLlama / FRED / Polymarket 的变量。拉不到的不放进来，模板里就会显示【需补充】。"""
    v = {"pm_block": "", "pm_list": ""}
    if d is None:
        return v
    for sym in DEFILLAMA_PROTOCOLS:
        for name in ("fees", "revenue", "holders_revenue"):
            for k in ("24h", "7d", "30d"):
                x = d.v("defi", sym, f"{name}_{k}")
                if x is not None:
                    v[f"{sym}_{name}_{k}"] = fmt_big(x)
    for name, short in (("stablecoin", "stable"), ("defi_tvl", "defi_tvl")):
        x, c = d.v("defi", "ALL", name), d.v("defi", "ALL", f"{name}_chg_7d")
        if x is not None:
            v[f"{short}_mcap" if short == "stable" else short] = fmt_big(x)
            v["defi_date"] = d.ref_date("defi", "ALL", name)
        if c is not None:
            v[f"{short}_7d"] = fmt_pct(c, MINUS)
    for name in FRED_SERIES:
        x, c = d.v("macro", name, "value"), d.v("macro", name, "chg_1w")
        if x is not None:
            v[name] = f"{x:.2f}%"
            v[f"{name}_date"] = d.ref_date("macro", name, "value")
            # macro_date 是美债收益率的日期。利率上限周末也有数，日期更新，不能拿来标收益率
            if name != "fed_upper":
                v.setdefault("macro_date", v[f"{name}_date"])
        if c is not None:
            v[f"{name}_chg_1w"] = f"{fmt_signed(c, MINUS, 2)} 个百分点"
    pm = d.rows("polymarket")
    # :g 保留 CSV 里的一位小数：0.3% 不会变成 0%，8.5% 和 7.5% 不会都变成 8%
    lines = [f"- {r['symbol']}：市场给 {float(r['value']):g}%" for _, r in pm.iterrows() if r["value"] != ""]
    if lines:
        v["pm_list"] = "\n".join(lines)
        v["pm_block"] = "\n市场怎么看（Polymarket）：\n" + v["pm_list"] + "\n"
    return v


def pred_vars(day: date) -> dict:
    try:
        from predictions import DONE, PENDING, load
        df = load()
    except Exception:
        return {}
    if df.empty:
        return {}
    v = {}
    done = df[df["状态"] == DONE].copy()
    if not done.empty:
        done["_d"] = pd.to_datetime(done["结算日期"]).dt.date
        v["pred_all_brier"] = f"{done['Brier'].astype(float).mean():.3f}"
        v["pred_count"] = str(len(done))
        wk = done[(done["_d"] > day - timedelta(days=7)) & (done["_d"] <= day)]
        if not wk.empty:
            v["pred_week_brier"] = f"{wk['Brier'].astype(float).mean():.3f}"
            v["pred_settled_list"] = "\n".join(
                f"- {r['问题']}：我给 {float(r['概率']):.0%}，{'发生' if int(r['结果']) == 1 else '没发生'}，"
                f"Brier {float(r['Brier']):.3f}" for _, r in wk.iterrows())
    new = df[(df["状态"] == PENDING) & (pd.to_datetime(df["发布日期"]).dt.date == day)]
    if not new.empty:
        v["pred_new_list"] = "\n".join(
            f"- {r['问题']}：{float(r['概率']):.0%}（{str(r['结算日期'])[:10]} 结算）" for _, r in new.iterrows())
    return v


def source_names(d: Daily, sections: list[str]) -> str:
    """回复里的一行来源：只写名字，去重，按栏目用到的数据块排。「（手填）」这种备注不写出去。"""
    names = []
    for sec in sections:
        for name in d.sources(sec).values():
            name = re.sub(r"（[^）]*）", "", name).strip()
            if name and name not in names:
                names.append(name)
    return "、".join(names)


def user_view(day: date) -> str | None:
    """data/views.csv 里当天写了看法就用它。"""
    if not VIEWS.exists():
        return None
    df = pd.read_csv(VIEWS, dtype=str, encoding="utf-8-sig").fillna("")
    hit = df[df["date"].str.strip() == day.isoformat()]
    return " ".join(hit.iloc[-1]["view"].split()) if not hit.empty and hit.iloc[-1]["view"].strip() else None


def auto_view(column: str, d: Daily | None, v: dict) -> str | None:
    """没给看法时，按当天数据写一句条件句。数据不够就返回 None（模板里会显示【需补充】）。"""
    if d is None:
        return None
    if column == "周一数据":
        s7, etf = d.v("defi", "ALL", "stablecoin_chg_7d"), d.v("etf", "BTC", "etf_net_flow")
        best, worst = v.get("best_7d"), v.get("worst_7d")
        if s7 is None or etf is None or not best or not worst:
            return None
        money = f"稳定币这周{'还在增加' if s7 > 0 else '在减少'}（{fmt_pct(s7, MINUS)}）"
        flow = f"BTC ETF 最近一个交易日{'净流入' if etf > 0 else '净流出'}"
        return (f"{money}，{flow}。如果这两个方向下周不变，我会继续偏向 {best} 这类强势币；"
                f"哪一个先反过来，就要先小心 {worst} 这种弱势币。")
    if column == "周四宏观":
        y, c = d.v("macro", "us5y", "value"), d.v("macro", "us5y", "chg_1w")
        if y is None or c is None:
            return None
        return (f"5 年期美债 {y:.2f}%，一周{'涨' if c > 0 else '跌'}了 {abs(c):.2f} 个百分点。"
                f"如果下周还在往上走，BTC 更难走出单边上涨；开始回落的话，风险资产的压力会小一些。")
    return None


def build_vars(day: date, column: str | None = None) -> dict:
    try:
        d = Daily(day.isoformat())
    except FileNotFoundError as e:
        print(f"注意：{e}")
        d = None
    v = {"date": day.isoformat()}
    v.update(price_vars(d))
    v.update(data_vars(d))
    v.update(pred_vars(day))
    if d is not None:
        secs = COLUMN_SECTIONS.get(column or "", ["price", "etf", "unlock", "defi", "macro", "polymarket"])
        v["sources"] = source_names(d, secs) or missing("数据来源")
    view = user_view(day) or auto_view(column or "", d, v)
    if view:
        v["view"] = view
    return v


class Fill(dict):
    def __missing__(self, key):
        return missing(key)


def fill(text: str, v: dict) -> str:
    # 只替换 {变量}，其他花括号原样保留
    fields = {f for _, f, _, _ in string.Formatter().parse(text) if f}
    for f in fields:
        text = text.replace("{" + f + "}", Fill(v)[f])
    return text


def auto_tag(text: str) -> str:
    """持有的币第一次出现没标「（我持有）」就自动补上。链接里的不动。"""
    for s in HOLDINGS:
        if f"{s}（我持有）" in text:
            continue
        text = re.sub(rf"(?<![A-Za-z/=.])(\$?{s})(?![A-Za-z）])", rf"\1（我持有）", text, count=1)
    return text


# ---------- 规则检查 ----------

def x_len(text: str) -> int:
    """X 的计数：链接算 23，中日韩字符算 2，其他算 1。"""
    text = re.sub(r"https?://\S+", "x" * 23, text)
    n = 0
    for ch in text:
        o = ord(ch)
        light = o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037
        n += 1 if light else 2
    return n


def check(parts: dict[str, str]) -> list[str]:
    main, reply, short = parts.get("主贴", ""), parts.get("回复", ""), parts.get("短推", "")
    issues = []
    for name, t in parts.items():
        for w in BANNED:
            if w in t:
                issues.append(f"{name}里有禁用词「{w}」，改成概率或「如果……那么……」")
        tags = re.findall(r"(?<![\w$])#[^\s#]+", t)
        if len(tags) > MAX_TAGS:
            issues.append(f"{name}有 {len(tags)} 个话题标签，最多 {MAX_TAGS} 个")
        for s in HOLDINGS:
            if re.search(rf"(?<![A-Za-z]){s}(?![A-Za-z])", t) and f"{s}（我持有）" not in t:
                issues.append(f"{name}提到了 {s}，但没标「（我持有）」")
        n = t.count("【需补充")
        if n:
            issues.append(f"{name}还有 {n} 处【需补充】")
    if DISCLAIMER not in main:
        issues.append(f"主贴结尾缺「{DISCLAIMER}」")
    if re.search(r"https?://", main):
        issues.append("主贴里有链接，来源链接要放到回复里")
    first2 = "\n".join(main.strip().splitlines()[:2])
    if not re.search(r"\d|？|\?", first2):
        issues.append("主贴前两行没有数字也没有问题，hook 不够")
    if short and x_len(short) > 280:
        issues.append(f"短推 {x_len(short)} 字符（按 X 计数），超过 280")
    return issues


# ---------- 主流程 ----------

def split_sections(text: str) -> dict[str, str]:
    parts, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^## (.+)$", line)
        if m:
            cur = m.group(1).strip()
            parts[cur] = []
        elif cur:
            parts[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in parts.items()}


def pick_variant(parts: dict[str, str], v: dict) -> dict[str, str]:
    """模板里「主贴·首期」这类段落：还没有任何已结算预测时替换同名段落，否则丢掉。"""
    first = "pred_count" not in v
    out = {k: t for k, t in parts.items() if not k.endswith("·首期")}
    if first:
        for k, t in parts.items():
            if k.endswith("·首期"):
                out[k.removesuffix("·首期")] = t
    return out


def template_for(column: str):
    matches = list(TEMPLATES.glob(f"*_{column}.md"))
    if not matches:
        raise SystemExit(f"找不到栏目模板 templates/*_{column}.md")
    return matches[0]


def todo_items(parts: dict[str, str]) -> list[str]:
    """主贴、回复、短推里所有【需补充：xxx】，去重，写在发布包最后。"""
    text = "\n".join(parts.get(k, "") for k in ("主贴", "回复", "短推"))
    return list(dict.fromkeys(re.findall(r"【需补充：[^】]*】", text)))


def intent(text: str) -> str:
    return "https://x.com/intent/post?text=" + quote(text)


def pack_json(day: date, column: str, parts: dict[str, str], images: list, issues: list[str],
              todo: list[str]) -> dict:
    """发布包.json 的内容。图片路径相对仓库根目录，比如 output/2026-09-28/price.png。"""
    def rel(p):
        try:
            return p.relative_to(ROOT).as_posix()
        except ValueError:
            return str(p)
    return {
        "date": day.isoformat(),
        "column": column,
        "main": parts.get("主贴", ""),
        "reply": parts.get("回复", ""),
        "short": parts.get("短推", ""),
        "images": [rel(p) for p in images],
        "checks": {"passed": not issues, "issues": issues},
        "todo": todo,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--column", choices=COLUMNS)
    a = ap.parse_args()
    day = date.fromisoformat(a.date)
    column = a.column or COLUMNS[day.weekday()]

    v = build_vars(day, column)
    parts = pick_variant(split_sections(fill(template_for(column).read_text(encoding="utf-8"), v)), v)
    parts = {k: auto_tag(t) for k, t in parts.items()}
    issues = check(parts)
    out_dir = OUTPUT / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = [f"{n}.png" for n in COLUMN_IMAGES.get(column, [])]
    images = [n for n in wanted if (out_dir / n).exists()] or sorted(p.name for p in out_dir.glob("*.png"))[:4]

    md = [f"# 发布包 {day}（{column}）", ""]
    for name in ("主贴", "回复", "短推"):
        if name not in parts:
            continue
        md += [f"## {name}（{x_len(parts[name])} 字符）", "", "```", parts[name], "```", ""]
        if name != "回复":
            md += [f"[一键发{name}]({intent(parts[name])})", ""]
    md += ["## 配图", ""] + ([f"- ![{p}]({p})" for p in images] or ["- 还没出图，先跑 make_table_image.py"]) + [""]
    md += ["## 规则检查", ""] + ([f"- [ ] {i}" for i in issues] or ["- 全部通过"]) + [""]
    todo = todo_items(parts)
    md += ["## 需补充", ""] + ([f"- [ ] {t}" for t in todo] or ["- 没有，数字都齐了"]) + [""]
    path = out_dir / "发布包.md"
    path.write_text("\n".join(md), encoding="utf-8")
    pack = pack_json(day, column, parts, [out_dir / p for p in images], issues, todo)
    (out_dir / "发布包.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{column} 发布包：{path}")
    for i in issues:
        print("  ⚠", i)
    for t in todo:
        print("  需补充：", t)


if __name__ == "__main__":
    main()
