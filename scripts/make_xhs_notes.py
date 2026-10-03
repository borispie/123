"""小红书笔记：每天一道量化面试概率题 → output/xhs/D01/ 里 5 张 3:4 图 + 笔记.md。

    python scripts/make_xhs_notes.py                         # 按发布顺序出前 14 篇
    python scripts/make_xhs_notes.py --days 15-30            # 出第 15–30 篇
    python scripts/make_xhs_notes.py --days 3 --start 2026-10-05   # 只出第 3 篇，日期从 10/5 算
    python scripts/make_xhs_notes.py --shop                  # 店铺开了以后：正文最后加一句引导
    python scripts/make_xhs_notes.py --no-images             # 只写文案，不出图（快）

题目、答案、模拟代码都在 products/quant_interview/questions.py。
图里「模拟」那一列的数，是现场跑卡片上那段代码得到的（seed = 0），别人复制代码运行会得到同样的数。

只生成文件，不会自动发。小红书禁止 AI 托管代发：图和文案自己看一遍，再手动发。
"""
from __future__ import annotations

import argparse
import html
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "products" / "quant_interview"))

from common import DISCLAIMER, MINUS, OUTPUT, launch_chromium  # noqa: E402
from questions import BY_ID, ORDER, check_rows, run_snippet  # noqa: E402

W, H = 1080, 1440
SERIES = "量化面试概率题"
# 正文里的自我介绍，想改就改这里
ABOUT_ME = "我是美本统计专业大四，暑假在新加坡做了量化实习。每天整理一道面试概率题，答案都用 Python 跑模拟验证过。"
SHOP_LINE = "完整 30 题（中英双语 + Python 验证代码 + AI 陪练提示词）放在主页店铺了。"
AI_NOTE = "（AI 辅助整理，题目和数字已用 Python 验证）"
TAGS = ["#量化面试", "#概率论", "#留学生求职", "#数据分析", "#统计学", "#面试题"]
TABS = ["封面", "题目", "解析", "模拟", "英文"]
FILES = ["1_封面.png", "2_题目.png", "3_解析.png", "4_模拟验证.png", "5_英文答法.png"]
TITLE_MAX, BODY_MAX = 20, 1000
# 小红书会限流或判违规的词：站外导流、赌、保证收益
BANNED = ["微信", "vx", "v信", "加v", "wx", "二维码", "http", "www.", "私聊", "赌", "稳赚", "必涨", "必跌", "保本"]

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", "WenQuanYi Zen Hei", sans-serif;
       color: #1a1a1a; }
#root { width: 1080px; height: 1440px; background: #fff; display: flex; flex-direction: column; overflow: hidden; }
.top { height: 96px; background: #1F4E78; color: #fff; display: flex; align-items: center;
       justify-content: space-between; padding: 0 48px; font-size: 34px; font-weight: 700; flex: none; }
.top .lv { font-size: 30px; letter-spacing: 4px; }
.fx { height: 72px; display: flex; align-items: center; border-bottom: 1px solid #d4d4d4; flex: none; font-size: 30px; }
.fx .ref { width: 112px; height: 100%; display: flex; align-items: center; justify-content: center;
           border-right: 1px solid #d4d4d4; color: #555; background: #f3f3f3; font-size: 26px; }
.fx .fxi { width: 72px; text-align: center; color: #888; font-style: italic; font-family: Georgia, serif; }
.fx .formula { color: #1a1a1a; white-space: nowrap; overflow: hidden; }
.body { flex: 1; position: relative; overflow: hidden; padding: 44px 60px 0; }
.tabs { height: 84px; background: #f3f3f3; border-top: 1px solid #d4d4d4; display: flex; align-items: stretch;
        padding-left: 28px; flex: none; font-size: 27px; color: #555; }
.tabs span { display: flex; align-items: center; padding: 0 24px; border-right: 1px solid #d4d4d4; }
.tabs span.on { background: #fff; color: #1F4E78; font-weight: 700; border-bottom: 5px solid #1F4E78; }
.tabs .site { margin-left: auto; border: none; color: #888; font-size: 23px; padding-right: 36px; }

/* 封面：一张 Excel 表，钩子写在选中的合并单元格里 */
.cover { padding: 0; }
.sheet { position: absolute; inset: 0;
         background-image: linear-gradient(#d9d9d9 1px, transparent 1px), linear-gradient(90deg, #d9d9d9 1px, transparent 1px);
         background-size: 169.33px 96px; background-position: 64px 44px; }
.colhdr { position: absolute; left: 0; top: 0; right: 0; height: 44px; display: flex; background: #f3f3f3;
          border-bottom: 1px solid #c8c8c8; }
.colhdr span { width: 169.33px; text-align: center; line-height: 44px; font-size: 22px; color: #666;
               border-right: 1px solid #d4d4d4; }
.colhdr .corner { width: 64px; }
.rowhdr { position: absolute; left: 0; top: 44px; bottom: 0; width: 64px; background: #f3f3f3;
          border-right: 1px solid #c8c8c8; overflow: hidden; }
.rowhdr span { display: block; height: 96px; line-height: 96px; text-align: center; font-size: 22px; color: #666;
               border-bottom: 1px solid #d4d4d4; }
.hook { position: absolute; left: 64px; width: 1016px; top: 140px; height: 672px; background: #fff;
        border: 5px solid #1F4E78; display: flex; flex-direction: column; justify-content: center; padding: 0 52px; }
.hook::after { content: ""; position: absolute; right: -11px; bottom: -11px; width: 16px; height: 16px;
               background: #1F4E78; border: 3px solid #fff; }
.hook div { font-weight: 900; line-height: 1.28; white-space: nowrap; }
.hook div.last { color: #1F4E78; }
.cellrow { position: absolute; left: 64px; height: 96px; display: flex; align-items: center; padding: 0 28px;
           font-size: 34px; }
.cellrow.ok { top: 908px; width: 677.33px; background: #C6EFCE; color: #006100; font-weight: 700; }
.cellrow.me { top: 1004px; width: 1016px; color: #555; background: #fff; }
.cellrow.tp { top: 812px; width: 1016px; color: #1F4E78; font-weight: 700; background: #fff; }

/* 内页：字号都乘 --k，出图时自动调到刚好填满卡片（见 FIT_JS） */
.body { --k: 1; --kc: 9; }
.chip { display: inline-block; background: #1F4E78; color: #fff; font-size: calc(30px * var(--k)); font-weight: 700;
        padding: 6px 22px; margin-bottom: calc(26px * var(--k)); }
.qzh { font-size: calc(40px * var(--k)); line-height: 1.62; margin-bottom: calc(30px * var(--k)); }
.qen { font-size: calc(28px * var(--k)); line-height: 1.5; color: #666; margin-bottom: calc(34px * var(--k));
       font-family: "Helvetica Neue", Arial, sans-serif; }
.note { background: #FFF2CC; border-left: 8px solid #BF9000; padding: 22px 28px; font-size: calc(32px * var(--k));
        line-height: 1.55; margin-bottom: calc(34px * var(--k)); }
.note b, .trap b, .fu b { display: block; font-size: calc(28px * var(--k)); margin-bottom: 6px; }
.next { font-size: calc(32px * var(--k)); color: #1F4E78; font-weight: 700; }
.ans { background: #C6EFCE; color: #006100; font-size: calc(40px * var(--k)); font-weight: 700; padding: 22px 28px;
       line-height: 1.45; margin-bottom: calc(30px * var(--k)); }
.ans .k { font-size: calc(28px * var(--k)); display: block; margin-bottom: 4px; }
ol.steps { padding-left: 0; list-style: none; counter-reset: s; margin-bottom: calc(28px * var(--k)); }
ol.steps li { counter-increment: s; font-size: calc(31px * var(--k)); line-height: 1.55;
              margin-bottom: calc(14px * var(--k)); padding-left: calc(58px * var(--k)); position: relative; }
ol.steps li::before { content: counter(s); position: absolute; left: 0; top: 0.12em; width: 1.36em; height: 1.36em;
                      background: #1F4E78; color: #fff; font-size: 0.84em; font-weight: 700; text-align: center;
                      line-height: 1.36em; }
.trap { background: #FFC7CE; color: #9C0006; padding: 20px 28px; font-size: calc(30px * var(--k)); line-height: 1.5; }
table.xl { border-collapse: collapse; width: 100%; table-layout: fixed; font-size: calc(27px * var(--k));
           margin-bottom: calc(30px * var(--k)); }
table.xl td { border: 1px solid #d4d4d4; height: calc(60px * var(--k)); padding: 0 14px; white-space: nowrap;
              overflow: hidden; }
table.xl td span.lab { display: inline-block; }
table.xl .colhdr2 td { background: #f3f3f3; color: #666; text-align: center; font-size: 20px; height: 32px; }
table.xl td.rn { background: #f3f3f3; color: #666; text-align: center; font-size: 20px; padding: 0; }
table.xl td.head { background: #1F4E78; color: #fff; font-weight: 700; text-align: center; }
table.xl td.r { text-align: right; font-variant-numeric: tabular-nums; }
table.xl td.good { background: #C6EFCE; color: #006100; }
pre.code { background: #F7F7F7; border: 1px solid #d4d4d4; padding: 22px 24px;
           font-size: calc(23px * min(var(--k), var(--kc)));
           line-height: 1.5; white-space: pre; overflow: hidden; margin-bottom: calc(20px * var(--k)); color: #1a1a1a;
           font-family: "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", "Noto Sans Mono CJK SC", "WenQuanYi Zen Hei Mono",
                        monospace; }
.small { font-size: calc(25px * var(--k)); color: #666; line-height: 1.5; }
.en { font-size: calc(31px * var(--k)); line-height: 1.6; background: #F2F6FA; border-left: 8px solid #1F4E78;
      padding: 24px 28px; margin-bottom: calc(30px * var(--k)); font-family: "Helvetica Neue", Arial, sans-serif; }
.fu { background: #FFF2CC; border-left: 8px solid #BF9000; padding: 20px 28px; font-size: calc(31px * var(--k));
      line-height: 1.55; margin-bottom: calc(30px * var(--k)); }
.tomorrow { font-size: calc(31px * var(--k)); color: #1F4E78; font-weight: 700; line-height: 1.5; }
.disc { margin-top: 18px; font-size: calc(25px * var(--k)); color: #888; }
"""


def esc(s) -> str:
    return html.escape(str(s))


def stars(level: int) -> str:
    return "★" * level + "☆" * (3 - level)


def em_width(s: str) -> float:
    """估算一行字有多少个「汉字宽」：汉字和全角符号算 1，数字字母空格算 0.55。"""
    return sum(1 if ord(c) > 0x2E80 else 0.55 for c in s)


def fmt_num(v: float | None, exact: float) -> str:
    if v is None:
        return "—"
    if abs(v) < 5e-10:
        v = 0.0
    if float(exact).is_integer():
        s = str(int(round(v))) if float(v).is_integer() else f"{v:.3f}"
    else:
        s = f"{v:.4f}"
    return s.replace("-", MINUS)


def page(day: int, q: dict, tab: int, body_html: str, body_cls: str = "") -> str:
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div id='root'>"
            f"<div class='top'><span>{SERIES} · Day {day:02d}</span><span class='lv'>{stars(q['level'])}</span></div>"
            f"<div class='fx'><span class='ref'>A{day}</span><span class='fxi'>fx</span>"
            f"<span class='formula'>{esc(q['fx'])}</span></div>"
            f"<div class='body {body_cls}'>{body_html}</div>"
            "<div class='tabs'>" + "".join(f"<span class='{'on' if i == tab else ''}'>{t}</span>"
                                           for i, t in enumerate(TABS))
            + "<span class='site'>答案经 Python 模拟验证</span></div>"
            "</div></body></html>")


def cover(day: int, q: dict) -> str:
    lines = q["hook"]
    size = int(min(118, 900 / max(em_width(x) for x in lines)))
    hook = "".join(f"<div class='{'last' if i == len(lines) - 1 else ''}' style='font-size:{size}px'>{esc(x)}</div>"
                   for i, x in enumerate(lines))
    cols = "".join(f"<span>{c}</span>" for c in "ABCDEF")
    rows = "".join(f"<span>{i}</span>" for i in range(1, 13))
    body = (f"<div class='sheet'></div><div class='colhdr'><span class='corner'></span>{cols}</div>"
            f"<div class='rowhdr'>{rows}</div>"
            f"<div class='hook'>{hook}</div>"
            f"<div class='cellrow tp'>题型：{esc(q['topic'])}</div>"
            "<div class='cellrow ok'>✓ 答案用 Python 模拟验证</div>"
            "<div class='cellrow me'>美本统计生 · 每天一道量化面试题</div>")
    return page(day, q, 0, body, "cover")


def question_card(day: int, q: dict) -> str:
    body = (f"<div class='chip'>题目</div><div class='qzh'>{esc(q['q_zh'])}</div>"
            f"<div class='qen'>{esc(q['q_en'])}</div>"
            f"<div class='note'><b>提示</b>{esc(q['hint'])}</div>"
            "<div class='next'>先自己想 30 秒，答案在下一张 →</div>")
    return page(day, q, 1, body)


def solution_card(day: int, q: dict) -> str:
    steps = "".join(f"<li>{esc(s)}</li>" for s in q["steps"])
    body = (f"<div class='ans'><span class='k'>答案</span>{esc(q['answer'])}</div>"
            f"<ol class='steps'>{steps}</ol>"
            f"<div class='trap'><b>常见错误</b>{esc(q['trap'])}</div>")
    return page(day, q, 2, body)


def sim_card(day: int, q: dict, rows) -> str:
    trs = ["<tr class='colhdr2'><td></td><td>A</td><td>B</td><td>C</td></tr>",
           "<tr><td class='rn'>1</td><td class='head'>项目</td><td class='head'>公式</td><td class='head'>模拟</td></tr>"]
    for i, (label, exact, sim, tol) in enumerate(rows, start=2):
        ok = sim is not None and abs(sim - exact) <= tol
        trs.append(f"<tr><td class='rn'>{i}</td><td><span class='lab'>{esc(label)}</span></td>"
                   f"<td class='r'>{fmt_num(exact, exact)}</td>"
                   f"<td class='r {'good' if ok else ''}'>{fmt_num(sim, exact)}</td></tr>")
    table = ("<table class='xl'><colgroup><col style='width:48px'><col style='width:560px'><col><col></colgroup>"
             + "".join(trs) + "</table>")
    body = (f"<div class='chip'>用 Python 模拟验证</div>{table}<pre class='code'>{esc(q['snippet'])}</pre>"
            "<div class='small'>import numpy as np 之后直接运行。seed = 0，跑出来的数和表里一样。</div>")
    return page(day, q, 3, body)


def english_card(day: int, q: dict, nxt: tuple[int, dict] | None) -> str:
    tomorrow = (f"<div class='tomorrow'>明天 Day {nxt[0]:02d}：{esc(nxt[1]['title'])}</div>" if nxt
                else "<div class='tomorrow'>30 题完结，评论区说说想看哪类题</div>")
    disc = f"<div class='disc'>{DISCLAIMER}</div>" if q.get("finance") else ""
    body = (f"<div class='chip'>面试这样说</div><div class='en'>{esc(q['say_en'])}</div>"
            f"<div class='fu'><b>追问</b>{esc(q['followup'])}</div>{tomorrow}{disc}")
    return page(day, q, 4, body)


def note_text(q: dict, shop: bool) -> tuple[str, str]:
    """(标题, 正文)"""
    hook = ""
    for i, x in enumerate(q["hook"]):
        hook += x if i == 0 or hook[-1] in "？！。，" else "，" + x
    parts = [
        hook,
        "量化 / 数据岗面试的经典题。先自己想 30 秒，再往后翻👉",
        "",
        "📌 题目",
        q["q_zh"],
        "",
        "图里有：解法、常见错误、Python 模拟验证、英文面试怎么答。",
        "",
        ABOUT_ME,
        "",
        "你的第一反应是多少？评论区说说👇",
    ]
    if shop:
        parts += ["", SHOP_LINE]
    parts += ["", AI_NOTE, "", " ".join(TAGS)]
    return q["title"], "\n".join(parts)


def check_note(title: str, body: str) -> list[str]:
    problems = []
    if len(title) > TITLE_MAX:
        problems.append(f"标题 {len(title)} 字，超过 {TITLE_MAX}")
    if len(body) > BODY_MAX:
        problems.append(f"正文 {len(body)} 字，超过 {BODY_MAX}")
    low = (title + body).lower()
    for w in BANNED:
        if w.lower() in low:
            problems.append(f"有容易被限流的词：{w}")
    if "AI 辅助" not in body:
        problems.append("正文没写 AI 辅助声明")
    return problems


def parse_days(s: str) -> list[int]:
    if s == "all":
        return list(range(1, len(ORDER) + 1))
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        else:
            out.append(int(part))
    bad = [d for d in out if not 1 <= d <= len(ORDER)]
    if bad:
        raise SystemExit(f"Day {bad} 不存在，只有 1–{len(ORDER)}")
    return out


# 内页：在 K_MIN–K_MAX 之间二分找最大的字号倍数，内容不超出卡片、代码和表格不被截断。
# 封面是固定排版，只检查。返回 [超出的像素, 有没有一行太宽]
K_MIN, K_MAX = 0.85, 1.4
FIT_JS = """() => {
    const b = document.querySelector('.body');
    const tooWide = () => [...b.querySelectorAll('.hook div, pre.code')]
            .some(e => e.scrollWidth > e.clientWidth + 1)
        || [...b.querySelectorAll('table.xl span.lab')]
            .some(e => e.offsetWidth > e.parentElement.clientWidth - 28);
    const extra = () => b.scrollHeight - b.clientHeight;
    if (b.classList.contains('cover')) return [extra(), tooWide()];
    // scrollHeight 不会小于盒子高度，所以量最后一个元素的底边
    const used = () => Math.max(...[...b.children].map(e => e.getBoundingClientRect().bottom))
        - b.getBoundingClientRect().top;
    const room = b.clientHeight - 36;
    const fits = () => used() <= room && !tooWide();
    const pre = b.querySelector('pre.code');
    if (pre) {  // 代码按最长的一行单独定字号上限，别把整张卡的字一起压小
        b.style.setProperty('--k', 1);
        const normal = pre.offsetWidth;        // 正常宽度
        pre.style.width = 'max-content';       // 不换行时实际要多宽
        const need = pre.offsetWidth;
        pre.style.width = '';
        b.style.setProperty('--kc', ((normal - 50) / (need - 50) * 0.97).toFixed(3));
    }
    let lo = %s, hi = %s;
    b.style.setProperty('--k', lo);
    if (!fits()) return [Math.round(Math.max(used() - room, 0)), tooWide()];
    for (let i = 0; i < 10; i++) {
        const mid = (lo + hi) / 2;
        b.style.setProperty('--k', mid);
        if (fits()) lo = mid; else hi = mid;
    }
    b.style.setProperty('--k', lo);
    return [0, false];
}""" % (K_MIN, K_MAX)


def render_all(jobs: list[tuple[str, Path]]):
    """一个浏览器出全部图。内容超出卡片就报错，告诉你是哪张。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = launch_chromium(p)
        pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        for page_html, path in jobs:
            pg.set_content(page_html)
            pg.evaluate("document.fonts.ready")
            over = pg.evaluate(FIT_JS)
            if over[0] > 1 or over[1]:
                browser.close()
                what = f"高了 {over[0]}px" if over[0] > 1 else "有一行太宽"
                raise ValueError(f"{path.parent.name}/{path.name} {what}，去 questions.py 删几个字")
            path.parent.mkdir(parents=True, exist_ok=True)
            pg.locator("#root").screenshot(path=str(path))
        browser.close()


def main():
    ap = argparse.ArgumentParser(description="出小红书笔记（图 + 文案），不会自动发")
    ap.add_argument("--days", default="1-14", help="第几篇：1-14 / 3 / 1,5,7 / all")
    ap.add_argument("--start", default=(date.today() + timedelta(days=1)).isoformat(), help="Day 1 的日期")
    ap.add_argument("--shop", action="store_true", help="店铺开了：正文加一句引导")
    ap.add_argument("--no-images", action="store_true", help="只写文案")
    ap.add_argument("--out", default=str(OUTPUT / "xhs"))
    a = ap.parse_args()

    out = Path(a.out)
    start = date.fromisoformat(a.start)
    days = parse_days(a.days)
    jobs, plan, all_problems = [], [], []
    for day in days:
        q = BY_ID[ORDER[day - 1]]
        nxt = (day + 1, BY_ID[ORDER[day]]) if day < len(ORDER) else None
        folder = out / f"D{day:02d}"
        when = start + timedelta(days=day - 1)
        title, body = note_text(q, a.shop)
        problems = check_note(title, body)
        all_problems += [f"Day {day:02d}：{x}" for x in problems]
        if not a.no_images:
            rows = check_rows(q, run_snippet(q))  # 现场跑卡片上的代码，表里的模拟值就是它的输出
            pages = [cover(day, q), question_card(day, q), solution_card(day, q), sim_card(day, q, rows),
                     english_card(day, q, nxt)]
            jobs += [(h, folder / f) for h, f in zip(pages, FILES)]
        folder.mkdir(parents=True, exist_ok=True)
        check_lines = "\n".join(f"- ⚠️ {x}" for x in problems) or "- 标题、正文长度和用词检查都通过了"
        (folder / "笔记.md").write_text(
            f"# Day {day:02d} · {q['id']}（{q['topic']}）\n\n"
            f"发布日期：{when.isoformat()}，建议北京时间晚上 8 点左右发（夏令时 = 美东早上 8 点，冬令时 = 美东早上 7 点）\n\n"
            f"## 标题（{len(title)}/{TITLE_MAX} 字）\n\n{title}\n\n"
            f"## 正文（{len(body)}/{BODY_MAX} 字）\n\n{body}\n\n"
            "## 图片（按顺序上传）\n\n" + "\n".join(f"{i}. {f}" for i, f in enumerate(FILES, 1)) + "\n\n"
            f"## 自动检查\n\n{check_lines}\n\n"
            "## 发之前自己看一眼\n\n"
            "- [ ] 图里的题目、答案自己读一遍，读得懂、没有错字\n"
            "- [ ] 发布页如果有「AI 生成 / 内容声明」之类的选项就勾上（以 App 当前界面为准）\n"
            "- [ ] 自己手动点发布，不用任何代发工具\n"
            "- [ ] 发完 1 小时内回前几条评论；48 小时后把数据填进 data/xhs_stats.csv\n",
            encoding="utf-8")
        plan.append(f"| {day:02d} | {when.isoformat()} | {q['id']} | {title} | {q['topic']} | {stars(q['level'])} |")
        print(f"Day {day:02d} {q['id']} {title}" + (f"  ⚠️ {'；'.join(problems)}" if problems else ""))

    if jobs:
        print(f"出图 {len(jobs)} 张……")
        render_all(jobs)
    (out / "发布计划.md").write_text(
        f"# 小红书发布计划（{SERIES}）\n\n每天 1 篇，图在 `D几/` 文件夹里，文案在同一个文件夹的 `笔记.md`。\n\n"
        "| Day | 日期 | 题号 | 标题 | 题型 | 难度 |\n|---|---|---|---|---|---|\n" + "\n".join(plan) + "\n",
        encoding="utf-8")
    print(f"完成 → {out}")
    if all_problems:
        print("要改的地方：\n" + "\n".join(all_problems))


if __name__ == "__main__":
    main()
