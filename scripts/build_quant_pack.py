"""打包要卖的产品：量化面试概率题 30 道 → output/products/ 里一个文件夹 + 一个 zip。

    python scripts/build_quant_pack.py                       # 打包
    python scripts/build_quant_pack.py --handle 你的小红书号   # PDF 每页底部印上小红书号，防转卖

包里有：PDF（题目册 + 解析册）、题库.md、Claude 陪练 Skill、通用提示词、verify.py、使用说明、商品主图。
PDF 和 verify.py 里的模拟数，都是现场跑题库里的代码得到的（seed = 0）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "products" / "quant_interview"))

from common import OUTPUT, launch_chromium  # noqa: E402
from make_xhs_notes import esc, fmt_num, stars  # noqa: E402
from questions import QUESTIONS, TOPICS, check_rows, run_snippet  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "products" / "quant_interview"
NAME = "量化面试概率题30道"
SKILL_DIR = "quant-interview-coach"


def ordered() -> list[dict]:
    """按题型 P E M G S、再按题号排。"""
    return sorted(QUESTIONS, key=lambda q: (list(TOPICS).index(q["id"][0]), int(q["id"][1:])))


# ---------- 题库.md（给 AI 读） ----------

def bank_md(qs: list[dict], results: dict) -> str:
    out = [f"# {NAME}（v1）\n",
           "量化 / 数据岗面试概率题。每道题：题目（中英）、提示、答案、解法、常见错误、英文答法、追问、Python 模拟验证。\n",
           "给 AI 陪练用：出题时只给「题目」，等对方作答后再看后面的内容。\n"]
    for q in qs:
        rows = results[q["id"]]
        out += [f"\n## {q['id']} · {q['topic']} · 难度 {stars(q['level'])}\n",
                f"**题目**：{q['q_zh']}\n",
                f"**Question**: {q['q_en']}\n",
                f"**提示**：{q['hint']}\n",
                f"**答案**：{q['answer']}\n",
                "**解法**：\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(q["steps"], 1)) + "\n",
                f"**常见错误**：{q['trap']}\n",
                f"**面试这样说**：{q['say_en']}\n",
                f"**追问**：{q['followup']}\n",
                "**Python 模拟验证**（seed = 0）：\n",
                "| 项目 | 公式 | 模拟 |\n|---|---|---|\n"
                + "\n".join(f"| {lab} | {fmt_num(ex, ex)} | {fmt_num(sim, ex)} |" for lab, ex, sim, _ in rows) + "\n",
                "```python\nimport numpy as np\n" + q["snippet"] + "\n```\n"]
    return "\n".join(out)


# ---------- verify.py（买家自己能跑） ----------

def verify_py(qs: list[dict]) -> str:
    out = [f'"""{NAME}（v1）· Python 模拟验证代码\n',
           "运行：pip install numpy，然后 python verify.py",
           "每道题的代码和 PDF 里一样（seed = 0），会打印「公式值」和「模拟值」。",
           '"""', "import numpy as np", "", ""]
    for q in qs:
        body = "\n".join("    " + line if line else "" for line in q["snippet"].splitlines())
        out += [f"def q_{q['id']}():", f'    """{q["title"]}"""', body, "    return locals()", "", ""]
    out.append("CHECKS = {")
    for q in qs:
        rows = ", ".join(f"({lab!r}, {float(ex)!r}, {expr!r})" for lab, ex, expr, _ in q["checks"])
        out.append(f"    {q['id']!r}: ({q['title']!r}, [{rows}]),")
    out += ["}", "", "",
            "def main():",
            "    for qid, (title, rows) in CHECKS.items():",
            "        ns = globals()[f'q_{qid}']()",
            "        print(f'{qid}  {title}')",
            "        for label, exact, expr in rows:",
            "            sim = '—' if expr is None else f'{float(eval(expr, {\"np\": np}, ns)):.4f}'",
            "            print(f'    {label}：公式 {exact:.4f}｜模拟 {sim}')",
            "", "",
            "if __name__ == '__main__':",
            "    main()", ""]
    return "\n".join(out)


# ---------- PDF ----------

PDF_CSS = """
@page { size: A4; margin: 15mm 15mm 17mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", "WenQuanYi Zen Hei", sans-serif; color: #1a1a1a;
       font-size: 12.5px; line-height: 1.6; }
.en { font-family: "Helvetica Neue", Arial, sans-serif; }
.page { page-break-after: always; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: center; }
.cover .bar { background: #1F4E78; color: #fff; padding: 26px 30px; }
.cover h1 { font-size: 34px; line-height: 1.3; }
.cover .sub { font-size: 16px; margin-top: 8px; opacity: .9; }
.cover .meta { margin-top: 26px; font-size: 14px; color: #444; line-height: 1.9; }
.ok { display: inline-block; background: #C6EFCE; color: #006100; padding: 2px 10px; margin: 0 6px 6px 0; font-size: 13px; }
h2 { font-size: 20px; color: #1F4E78; border-bottom: 3px solid #1F4E78; padding-bottom: 6px; margin-bottom: 14px; }
table.toc { border-collapse: collapse; width: 100%; font-size: 11.5px; line-height: 1.35; }
table.toc td, table.toc th { border: 1px solid #d4d4d4; padding: 3px 8px; }
table.toc th { background: #1F4E78; color: #fff; }
.howto { background: #F2F6FA; border-left: 5px solid #1F4E78; padding: 10px 14px; margin-bottom: 16px; }
.q { page-break-inside: avoid; border: 1px solid #d4d4d4; margin-bottom: 12px; }
.q .hd { background: #f3f3f3; border-bottom: 1px solid #d4d4d4; padding: 5px 12px; font-weight: 700; display: flex;
         justify-content: space-between; }
.q .hd span:last-child { color: #1F4E78; font-weight: 400; }
.q .zh { padding: 8px 12px 2px; font-size: 13.5px; }
.q .qe { padding: 0 12px 8px; color: #666; font-size: 11.5px; line-height: 1.45; }
.q .draft { height: 70px; margin: 0 12px 10px; border: 1px dashed #c8c8c8; color: #aaa; font-size: 10px; padding: 3px 6px; }
.sol .hd2 { background: #1F4E78; color: #fff; padding: 8px 14px; font-size: 16px; font-weight: 700; display: flex;
            justify-content: space-between; margin-bottom: 10px; }
.sol .qz { margin-bottom: 10px; }
.box { padding: 7px 12px; margin-bottom: 9px; }
.box b { display: block; font-size: 11.5px; }
.ansb { background: #C6EFCE; color: #006100; font-size: 15px; font-weight: 700; }
.trapb { background: #FFC7CE; color: #9C0006; }
.fub { background: #FFF2CC; border-left: 4px solid #BF9000; }
.saye { background: #F2F6FA; border-left: 4px solid #1F4E78; }
ol { margin: 0 0 9px 20px; }
ol li { margin-bottom: 2px; }
table.xl { border-collapse: collapse; width: 100%; font-size: 11.5px; margin-bottom: 8px; }
table.xl td { border: 1px solid #d4d4d4; padding: 3px 8px; }
table.xl td.h { background: #1F4E78; color: #fff; font-weight: 700; text-align: center; }
table.xl td.r { text-align: right; font-variant-numeric: tabular-nums; }
table.xl td.good { background: #C6EFCE; color: #006100; }
pre { background: #F7F7F7; border: 1px solid #d4d4d4; padding: 7px 10px; font-size: 10px; line-height: 1.45;
      font-family: "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", "WenQuanYi Zen Hei Mono", monospace; white-space: pre; }
"""


def pdf_html(qs: list[dict], results: dict) -> str:
    counts = {k: sum(q["id"][0] == k for q in qs) for k in TOPICS}
    toc = "".join(f"<tr><td>{q['id']}</td><td>{esc(q['title'])}</td><td>{esc(q['topic'])}</td>"
                  f"<td>{stars(q['level'])}</td></tr>" for q in qs)
    parts = [f"<html><head><meta charset='utf-8'><style>{PDF_CSS}</style></head><body>",
             "<div class='page cover'><div class='bar'>"
             "<h1>量化 / 数据岗面试<br>概率题 30 道</h1><div class='sub'>中英双语 · 每题 Python 模拟验证 · 附 AI 陪练 · v1</div>"
             "</div><div class='meta'>"
             + "".join(f"<span class='ok'>{TOPICS[k]} {n} 道</span>" for k, n in counts.items())
             + "<br>适合：量化研究 / 量化交易 / 数据科学 / 数据分析岗面试"
             "<br>每道题：题目（中英）· 提示 · 答案 · 解法 · 常见错误 · 英文答法 · 追问 · Python 模拟"
             "</div></div>",
             "<div class='page'><h2>怎么用</h2><div class='howto'>"
             "1. 先做「题目册」：每道题限时 5 分钟，边想边小声说出来（面试就是这样）。<br>"
             "2. 做完再翻「解析册」：先对答案，再看解法和常见错误，最后照着「面试这样说」用英文讲一遍。<br>"
             "3. 想有人陪练：用包里的 Claude Skill 或通用提示词，让 AI 一题一题出题、判分、追问。<br>"
             "4. 想验证答案：运行 verify.py，模拟值和公式值对得上。"
             f"</div><h2>目录</h2><table class='toc'><tr><th>题号</th><th>题目</th><th>题型</th><th>难度</th></tr>{toc}"
             "</table></div>",
             "<h2>题目册</h2>"]
    for q in qs:
        parts.append(f"<div class='q'><div class='hd'><span>{q['id']} · {esc(q['topic'])}</span>"
                     f"<span>{stars(q['level'])}</span></div>"
                     f"<div class='zh'>{esc(q['q_zh'])}</div><div class='qe en'>{esc(q['q_en'])}</div>"
                     "<div class='draft'>草稿</div></div>")
    parts.append("<div class='page'></div><h2>解析册</h2>")
    for i, q in enumerate(qs):
        rows = "".join(
            f"<tr><td>{esc(lab)}</td><td class='r'>{fmt_num(ex, ex)}</td>"
            f"<td class='r {'good' if sim is not None and abs(sim - ex) <= tol else ''}'>{fmt_num(sim, ex)}</td></tr>"
            for lab, ex, sim, tol in results[q["id"]])
        steps = "".join(f"<li>{esc(s)}</li>" for s in q["steps"])
        brk = " page" if i < len(qs) - 1 else ""
        parts.append(
            f"<div class='sol{brk}'><div class='hd2'><span>{q['id']} · {esc(q['topic'])}</span>"
            f"<span>{stars(q['level'])}</span></div>"
            f"<div class='qz'>{esc(q['q_zh'])}</div>"
            f"<div class='box ansb'><b>答案</b>{esc(q['answer'])}</div>"
            f"<b>解法</b><ol>{steps}</ol>"
            f"<div class='box trapb'><b>常见错误</b>{esc(q['trap'])}</div>"
            f"<div class='box saye en'><b>面试这样说</b>{esc(q['say_en'])}</div>"
            f"<div class='box fub'><b>追问</b>{esc(q['followup'])}</div>"
            "<b>Python 模拟验证（seed = 0）</b>"
            f"<table class='xl'><tr><td class='h'>项目</td><td class='h'>公式</td><td class='h'>模拟</td></tr>{rows}</table>"
            f"<pre>import numpy as np\n{esc(q['snippet'])}</pre></div>")
    parts.append("</body></html>")
    return "".join(parts)


# ---------- 商品主图（1:1） ----------

COVER_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", "WenQuanYi Zen Hei", sans-serif; }
#root { width: 1080px; height: 1080px; background: #fff; position: relative; overflow: hidden;
        background-image: linear-gradient(#e2e2e2 1px, transparent 1px), linear-gradient(90deg, #e2e2e2 1px, transparent 1px);
        background-size: 169.33px 80px; background-position: 64px 0; }
.top { background: #1F4E78; color: #fff; padding: 46px 64px 40px; }
.top h1 { font-size: 84px; line-height: 1.15; font-weight: 900; }
.top div { font-size: 36px; margin-top: 14px; opacity: .92; }
.list { margin: 48px 64px 0; }
.item { background: #fff; border: 2px solid #d4d4d4; font-size: 40px; padding: 18px 26px; margin-bottom: 16px; }
.item.ok { background: #C6EFCE; color: #006100; border-color: #C6EFCE; font-weight: 700; }
.foot { position: absolute; left: 64px; right: 64px; bottom: 40px; font-size: 30px; color: #555; }
"""


def main_image_html() -> str:
    items = ["✓ 每题 Python 模拟验证，附代码", "中英双语题目 + 面试英文答法",
             "AI 陪练：Claude / DeepSeek / Kimi 都能用", "条件概率 · 期望 · 随机过程 · 几何概率 · 统计"]
    lis = "".join(f"<div class='item {'ok' if i == 0 else ''}'>{esc(x)}</div>" for i, x in enumerate(items))
    return (f"<html><head><meta charset='utf-8'><style>{COVER_CSS}</style></head><body><div id='root'>"
            "<div class='top'><h1>量化面试<br>概率题 30 道</h1><div>量化 / 数据岗面试高频题 · v1</div></div>"
            f"<div class='list'>{lis}</div><div class='foot'>PDF 题目册 + 解析册 · 题库 · 验证代码 · AI 陪练提示词</div>"
            "</div></body></html>")


def render(pdf_page_html: str, pdf_path: Path, img_html: str, img_path: Path, footer: str):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = launch_chromium(p)
        pg = browser.new_page()
        pg.set_content(pdf_page_html)
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(pdf_path), format="A4", print_background=True, display_header_footer=True,
               header_template="<div></div>",
               footer_template=("<div style=\"width:100%;font-size:8px;color:#888;text-align:center;"
                                "font-family:'Noto Sans CJK SC','PingFang SC','WenQuanYi Zen Hei',sans-serif\">"
                                f"<span class='pageNumber'></span> / <span class='totalPages'></span> · {esc(footer)}</div>"),
               margin={"top": "15mm", "bottom": "17mm", "left": "15mm", "right": "15mm"})
        img = browser.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=2)
        img.set_content(img_html)
        img.evaluate("document.fonts.ready")
        img.locator("#root").screenshot(path=str(img_path))
        browser.close()


def main():
    ap = argparse.ArgumentParser(description="打包量化面试题产品")
    ap.add_argument("--handle", default="", help="小红书号，印在 PDF 每页底部")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--out", default=str(OUTPUT / "products"))
    a = ap.parse_args()

    qs = ordered()
    results = {}
    for q in qs:
        rows = check_rows(q, run_snippet(q))
        bad = [r for r in rows if r[2] is not None and abs(r[2] - r[1]) > r[3]]
        if bad:
            raise SystemExit(f"{q['id']} 模拟和公式对不上：{bad}，先修 questions.py")
        results[q["id"]] = rows
    print(f"{len(qs)} 道题的模拟都和公式对上了")

    pack = Path(a.out) / f"{NAME}_{a.version}"
    if pack.exists():
        shutil.rmtree(pack)
    skill = pack / SKILL_DIR
    skill.mkdir(parents=True)

    md, py = bank_md(qs, results), verify_py(qs)
    for d in (pack, skill):
        (d / "题库.md").write_text(md, encoding="utf-8")
        (d / "verify.py").write_text(py, encoding="utf-8")
    shutil.copy(SRC / "SKILL.md", skill / "SKILL.md")
    shutil.copy(SRC / "通用提示词.md", pack / "通用提示词.md")
    shutil.copy(SRC / "使用说明.md", pack / "使用说明.md")

    footer = "仅限购买者个人学习使用，请勿转发或转卖" + (f" · 小红书：{a.handle}" if a.handle else "")
    pdf_path = pack / f"{NAME}_{a.version}.pdf"
    img_path = Path(a.out) / f"{NAME}_{a.version}_商品主图.png"
    render(pdf_html(qs, results), pdf_path, main_image_html(), img_path, footer)

    zip_path = shutil.make_archive(str(Path(a.out) / f"{NAME}_{a.version}"), "zip", root_dir=pack.parent,
                                   base_dir=pack.name)
    print(f"产品文件夹 → {pack}")
    print(f"压缩包（发给买家）→ {zip_path}")
    print(f"商品主图（店铺用，不放进压缩包）→ {img_path}")
    if not a.handle:
        print("提示：加 --handle 你的小红书号，PDF 每页底部会印上，别人转卖时能看出来源")


if __name__ == "__main__":
    main()
