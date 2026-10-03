"""找工作：每天搜一遍岗位，按我的简历打分，只列出新的、合适的。

python scripts/job_search.py              # 搜 + 出 job-search/岗位_日期.md
python scripts/job_search.py --all        # 连之前看过的也列出来
python scripts/job_search.py --pages 5    # aidevboard 每个关键词最多翻 5 页（默认 15）

来源：
1. aidevboard.com（按关键词搜，再打开详情页看要求）
2. data/job_companies.csv 里列的公司，直接读它们 Greenhouse / Lever / Ashby 的公开岗位接口
   （云端要在 Network access 里放行 boards-api.greenhouse.io、api.lever.co、api.ashbyhq.com）

只负责找和筛，不会帮你提交。结果和「看过的岗位」存在 job-search/（不上传 GitHub）。
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

from common import DATA, ROOT, get

OUT = ROOT / "job-search"
SEEN = OUT / "seen.csv"
COMPANIES = DATA / "job_companies.csv"

BOARD = "https://aidevboard.com"
BOARD_QUERIES = [
    {"level": "junior"}, {"q": "analyst"}, {"q": "data scientist"}, {"q": "quant"},
    {"q": "research analyst"}, {"q": "risk"}, {"q": "statistics"}, {"q": "crypto"},
    {"q": "blockchain"}, {"q": "graduate"}, {"q": "intern"}, {"q": "evaluation"},
]

# ---------- 标题筛选 ----------
TITLE_OK = re.compile(
    r"analyst|analytics|data scien|quant|research associate|risk|insights|business intelligence|"
    r"evaluat|data quality|forecast|pricing|actuar|statistic|graduate|new grad|early career|"
    r"accelerator|campus|trainee|rotation", re.I)
TITLE_BAD = re.compile(
    r"senior|\bsr\b|staff|principal|\blead\b|manager|director|head of|\bvp\b|vice president|"
    r"\bII\b|\bIII\b|\bIV\b|engineer|developer|sales|account exec|recruit|design|legal|counsel|"
    r"ph\.?d|security|soc analyst|it analyst|compliance", re.I)

# ---------- 地点 ----------
# 没有工作签证的地方（美国 OPT 只能在美国用）
LOC_BAD = re.compile(
    r"london|\buk\b|united kingdom|england|paris|france|germany|berlin|munich|madrid|barcelona|"
    r"spain|amsterdam|netherlands|dublin|ireland|india|bangalore|bengaluru|hyderabad|delhi|"
    r"israel|tel aviv|toronto|canada|montreal|vancouver|mexico|brazil|argentina|australia|"
    r"sydney|japan|tokyo|korea|seoul|poland|warsaw|sweden|stockholm|switzerland|zurich|dubai|"
    r"abu dhabi|vietnam|hanoi|taipei|taiwan|europe|emea|latam", re.I)
LOC_OK = re.compile(
    r"united states|\busa?\b|remote \(us\)|anywhere|global|asia|singapore|hong kong|china|"
    r"shanghai|beijing|shenzhen|new york|san francisco|chicago|boston|seattle|austin|"
    r"pennsylvania|philadelphia|pittsburgh", re.I)
US_STATE = re.compile(  # 「Chicago, IL」这种，大小写敏感，免得把「London, UK」算进来
    r", (AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|"
    r"NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY)\b")

# ---------- 详情页里的硬伤和加分 ----------
CITIZEN = re.compile(r"u\.?s\.? citizen|green card|permanent resident|\bitar\b|security clearance|"
                     r"u\.?s\.? person", re.I)
NO_SPONSOR = re.compile(
    r"(unable|not able|cannot|can't|do not|does not|will not|won't|are not)\s+(to\s+)?"
    r"(currently\s+)?(sponsor|provide (visa )?sponsorship|support (visa )?sponsorship)|"
    r"without (the need for )?(visa )?sponsorship|no (visa )?sponsorship|f-1 opt", re.I)
ENROLLED = re.compile(r"currently (enrolled|pursuing)|returning to school|must be (a )?(current )?student",
                      re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(\d{1,2})?\+?\s*years?", re.I)
NEW_GRAD = re.compile(r"new grad|recent grad|early career|entry[- ]level|graduates|0\s*[-–]\s*[12]\s*years|"
                      r"no experience required|university students", re.I)
CRYPTO = re.compile(r"crypto|blockchain|web3|\bdefi\b|digital asset|stablecoin|on-?chain|bitcoin", re.I)
TRADING = re.compile(r"quant|trading|trader|capital|point72|akuna|jump", re.I)  # 只看标题和公司名
SKILLS = re.compile(r"\bsql\b|\bpython\b|\br\b(?! ?&)|statistic|a/b|experiment|\bexcel\b|forecast|"
                    r"regression|probabilit", re.I)


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    salary: str = ""
    text: str = ""
    score: int = 0
    tier: str = ""
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.url


def _text(fragment: str) -> list[str]:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", fragment, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    return [ln.strip() for ln in t.split("\n") if ln.strip() and ln.strip() != "·"]


# ---------- aidevboard ----------
def parse_board_list(page: str) -> list[Job]:
    """列表页 → 岗位（标题、公司、地点、薪资）。"""
    jobs = []
    for part in re.split(r'(?=<a[^>]+href="/job/)', page)[1:]:
        url = re.match(r'<a[^>]+href="(/job/[^"]+)"', part).group(1)
        lines = []
        for ln in _text(part[:6000]):
            if ln.startswith("Hiring AI") or ln.startswith("Page "):
                break
            lines.append(ln)
            if re.search(r"\bago$|today|yesterday", ln):
                break
        if len(lines) < 3:
            continue
        salary = lines[3] if len(lines) > 3 and "$" in lines[3] else ""
        jobs.append(Job(lines[0], lines[1], lines[2], BOARD + url, "aidevboard", salary))
    return jobs


def parse_board_detail(page: str) -> str:
    lines = _text(page)
    try:
        a, b = lines.index("About this role"), lines.index("Job Details")
    except ValueError:
        return "\n".join(lines)
    return "\n".join(lines[a + 1:b])


def fetch_board(pages: int) -> list[Job]:
    found: dict[str, Job] = {}
    for q in BOARD_QUERIES:
        for p in range(1, pages + 1):
            try:
                page = get(f"{BOARD}/?{urlencode({**q, 'page': p})}").text
            except RuntimeError as e:
                print(f"aidevboard 拉不到：{e}", file=sys.stderr)
                break
            for j in parse_board_list(page):
                found.setdefault(j.key, j)
            if 'rel="next"' not in page:
                break
            time.sleep(0.3)
    return list(found.values())


# ---------- Greenhouse / Lever / Ashby ----------
def parse_greenhouse(data: dict, company: str) -> list[Job]:
    return [Job(j.get("title", ""), company, (j.get("location") or {}).get("name", ""),
                j.get("absolute_url", ""), "greenhouse",
                text="\n".join(_text(html.unescape(j.get("content", "")))))
            for j in data.get("jobs", [])]


def parse_lever(data: list, company: str) -> list[Job]:
    jobs = []
    for j in data:
        lists = "\n".join(f"{x.get('text', '')}\n" + "\n".join(_text(x.get("content", "")))
                          for x in j.get("lists", []))
        text = "\n".join([j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")])
        cat = j.get("categories") or {}
        loc = cat.get("location", "")
        if j.get("workplaceType") == "remote" and "remote" not in loc.lower():
            loc = f"{loc} (Remote)".strip()
        jobs.append(Job(j.get("text", ""), company, loc, j.get("hostedUrl", ""), "lever", text=text))
    return jobs


def parse_ashby(data: dict, company: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "")
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = f"{loc} (Remote)".strip()
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "") or ""
        jobs.append(Job(j.get("title", ""), company, loc, j.get("jobUrl", ""), "ashby",
                        salary=comp, text=j.get("descriptionPlain", "")))
    return jobs


ATS = {
    "greenhouse": ("https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", parse_greenhouse),
    "lever": ("https://api.lever.co/v0/postings/{slug}?mode=json", parse_lever),
    "ashby": ("https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", parse_ashby),
}


def load_companies() -> list[dict]:
    if not COMPANIES.exists():
        return []
    with COMPANIES.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("slug")]


def fetch_companies(errors: list[str]) -> list[Job]:
    jobs = []
    for c in load_companies():
        url, parse = ATS[c["ats"]]
        try:
            jobs += parse(get(url.format(slug=c["slug"]), tries=2).json(), c["company"])
        except (RuntimeError, ValueError) as e:
            errors.append(f"{c['company']}（{c['ats']}/{c['slug']}）：{str(e)[:120]}")
    return jobs


# ---------- 打分 ----------
def min_years(text: str) -> int | None:
    """要求的最少工作年限。只看提到 experience 的句子，取最小的那个。"""
    found = []
    for sent in re.split(r"[\n.;]", text):
        if not re.search(r"experience", sent, re.I):
            continue
        for m in YEARS.finditer(sent):
            n = int(m.group(1))
            if n <= 15:
                found.append(n)
    return min(found) if found else None


def salary_floor(salary: str) -> int | None:
    """「$120k - $187k」→ 120（单位 k）。"""
    m = re.search(r"\$(\d+)k", salary)
    return int(m.group(1)) if m else None


def needs_grad_degree(text: str) -> bool:
    for sent in re.split(r"[\n.;]", text):
        if re.search(r"master|ph\.?d|\bms\b|\bmsc\b|\bm\.s\.", sent, re.I) and \
                re.search(r"pursuing|required|requirement|minimum|must|degree in", sent, re.I) and \
                not re.search(r"bachelor|\bbs\b|\bb\.s\.|\bba\b|undergrad|equivalent (practical |work )?experience",
                              sent, re.I):
            return True
    return False


def score(job: Job) -> Job:
    t, text, loc = job.title, job.text, job.location
    if not TITLE_OK.search(t) or TITLE_BAD.search(t):
        job.tier = "skip"
        return job
    if LOC_BAD.search(loc) and not (LOC_OK.search(loc) or US_STATE.search(loc)):
        job.blockers.append(f"地点 {loc}，没有工作签证")
    if CITIZEN.search(text):
        job.blockers.append("要美国公民 / 绿卡")
    if NO_SPONSOR.search(text):
        job.blockers.append("写了不支持签证（OPT 可能也不收）")
    if needs_grad_degree(text):
        job.blockers.append("要硕士或博士")
    yrs = min_years(text)
    if yrs is not None and yrs >= 3:
        job.blockers.append(f"要 {yrs}+ 年经验")
    elif yrs == 2:
        job.score -= 2
        job.reasons.append("要 2 年经验（可以冲）")
    elif yrs is not None:
        job.score += 1
        job.reasons.append(f"只要 {yrs} 年经验")
    if ENROLLED.search(text):
        job.score -= 2
        job.reasons.append("要求在读，你 12 月毕业，先确认")
    if NEW_GRAD.search(text) or NEW_GRAD.search(t):
        job.score += 3
        job.reasons.append("招应届生")
    if CRYPTO.search(t + " " + job.company + " " + text[:3000]):
        job.score += 2
        job.reasons.append("币圈相关")
    elif TRADING.search(t + " " + job.company):
        job.score += 1
        job.reasons.append("量化 / 交易")
    low = salary_floor(job.salary)
    if low and low >= 150:
        job.score -= 2
        job.reasons.append(f"起薪 ${low}k，一般要多年经验")
    hits = {m.group(0).lower() for m in SKILLS.finditer(text)}
    if hits:
        job.score += min(len(hits), 4)
        job.reasons.append("用到：" + "、".join(sorted(hits)[:5]))
    if re.search(r"remote|anywhere", loc, re.I):
        job.score += 1
        job.reasons.append("远程")
    if not text:
        job.reasons.append("没拿到详情，自己点开看要求")
    job.tier = "no" if job.blockers else ("top" if job.score >= 5 else "maybe")
    return job


# ---------- 看过的 ----------
def load_seen() -> set[str]:
    if not SEEN.exists():
        return set()
    with SEEN.open(encoding="utf-8") as f:
        return {r["url"] for r in csv.DictReader(f)}


def save_seen(jobs: list[Job], day: str) -> None:
    new = not SEEN.exists()
    with SEEN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["url", "title", "company", "first_seen"])
        for j in jobs:
            w.writerow([j.url, j.title, j.company, day])


# ---------- 输出 ----------
def _cell(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ")


def render(jobs: list[Job], day: str, errors: list[str], total: int) -> str:
    top = sorted([j for j in jobs if j.tier == "top"], key=lambda j: -j.score)
    maybe = sorted([j for j in jobs if j.tier == "maybe"], key=lambda j: -j.score)
    no = [j for j in jobs if j.tier == "no"]
    out = [f"# 岗位 {day}", "",
           f"一共扫了 {total} 个岗位，标题对口的新岗位 {len(top) + len(maybe) + len(no)} 个："
           f"推荐 {len(top)}、可以试 {len(maybe)}、不合适 {len(no)}。",
           "投之前点开再看一遍要求。投了就在 `投递清单.md` 里记一下。", ""]
    for name, group in (("推荐投", top), ("可以试", maybe)):
        out += [f"## {name}", ""]
        if not group:
            out += ["（没有）", ""]
            continue
        out += ["| 分 | 岗位 | 公司 | 地点 | 薪资 | 为什么 |", "|---|---|---|---|---|---|"]
        for j in group:
            out.append(f"| {j.score} | [{_cell(j.title)}]({j.url}) | {_cell(j.company)} | {_cell(j.location)} "
                       f"| {_cell(j.salary)} | {_cell('；'.join(j.reasons))} |")
        out.append("")
    if no:
        out += ["## 不合适（帮你排掉的）", ""]
        out += [f"- {j.title} · {j.company}：{'；'.join(j.blockers)}" for j in no]
        out.append("")
    if errors:
        out += ["## 没拉到的公司", ""] + [f"- {e}" for e in errors] + [""]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="之前看过的也列出来")
    ap.add_argument("--pages", type=int, default=15, help="aidevboard 每个关键词最多翻几页")
    args = ap.parse_args()
    day = date.today().isoformat()
    OUT.mkdir(exist_ok=True)

    errors: list[str] = []
    jobs = fetch_board(args.pages) + fetch_companies(errors)
    total = len(jobs)
    seen = set() if args.all else load_seen()
    fresh = [j for j in {j.key: j for j in jobs}.values() if j.key not in seen]

    for j in fresh:
        j.tier = "" if TITLE_OK.search(j.title) and not TITLE_BAD.search(j.title) else "skip"
    for j in fresh:  # 只给标题对口的 aidevboard 岗位开详情页
        if j.tier != "skip" and j.source == "aidevboard" and not j.text:
            try:
                j.text = parse_board_detail(get(j.url).text)
            except RuntimeError:
                pass
            time.sleep(0.3)
    fresh = [score(j) for j in fresh]

    path = OUT / f"岗位_{day}.md"
    path.write_text(render([j for j in fresh if j.tier != "skip"], day, errors, total), encoding="utf-8")
    if not args.all:
        save_seen(fresh, day)
    top = sum(j.tier == "top" for j in fresh)
    maybe = sum(j.tier == "maybe" for j in fresh)
    print(f"新岗位：推荐 {top}，可以试 {maybe} → {path}")


if __name__ == "__main__":
    main()
