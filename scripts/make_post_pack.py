"""按当天栏目生成发布包：主贴、回复、短推、一键发帖链接 + 规则检查。

    python scripts/make_post_pack.py                    # 今天
    python scripts/make_post_pack.py --date 2026-09-28
    python scripts/make_post_pack.py --column 周二代币经济   # 不按星期，指定栏目

输出 output/日期/发布包.md。数字只从 data/日期.csv 和 data/predictions.xlsx 来，
没有的一律是【需补充：xxx】。最后会列出违反 CLAUDE.md 发帖规则的地方。
"""
from __future__ import annotations

import argparse
import re
import string
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd

from common import COINS, DISCLAIMER, HOLDINGS, OUTPUT, TEMPLATES, Daily, fmt_big, fmt_pct, fmt_price, fmt_signed, missing

COLUMNS = ["周一数据", "周二代币经济", "周三链上巨鲸", "周四宏观", "周五项目深度", "周六统计小课", "周日预测复盘"]
BANNED = ["必涨", "必跌", "稳了"]
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


def build_vars(day: date) -> dict:
    try:
        d = Daily(day.isoformat())
    except FileNotFoundError as e:
        print(f"注意：{e}")
        d = None
    v = {"date": day.isoformat()}
    v.update(price_vars(d))
    v.update(pred_vars(day))
    if d is not None:
        v["sources"] = "\n".join(f"{name}: {u}" for u, name in d.sources().items()) or missing("数据来源链接")
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


def intent(text: str) -> str:
    return "https://x.com/intent/post?text=" + quote(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--column", choices=COLUMNS)
    a = ap.parse_args()
    day = date.fromisoformat(a.date)
    column = a.column or COLUMNS[day.weekday()]

    v = build_vars(day)
    parts = pick_variant(split_sections(fill(template_for(column).read_text(encoding="utf-8"), v)), v)
    parts = {k: auto_tag(t) for k, t in parts.items()}
    issues = check(parts)
    out_dir = OUTPUT / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(p.name for p in out_dir.glob("*.png"))

    md = [f"# 发布包 {day}（{column}）", ""]
    for name in ("主贴", "回复", "短推"):
        if name not in parts:
            continue
        md += [f"## {name}（{x_len(parts[name])} 字符）", "", "```", parts[name], "```", ""]
        if name != "回复":
            md += [f"[一键发{name}]({intent(parts[name])})", ""]
    md += ["## 配图", ""] + ([f"- ![{p}]({p})" for p in images] or ["- 还没出图，先跑 make_table_image.py"]) + [""]
    md += ["## 规则检查", ""] + ([f"- [ ] {i}" for i in issues] or ["- 全部通过"]) + [""]
    path = out_dir / "发布包.md"
    path.write_text("\n".join(md), encoding="utf-8")

    print(f"{column} 发布包：{path}")
    for i in issues:
        print("  ⚠", i)


if __name__ == "__main__":
    main()
