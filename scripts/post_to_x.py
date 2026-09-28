"""把 output/日期/发布包.json 发到自己的 X 账号（X API v2 + OAuth 1.0a 用户上下文）。

    python scripts/post_to_x.py                                   # 预览今天的，不发
    python scripts/post_to_x.py --view "如果……那么……"             # 预览，把「我的看法：【需补充…】」换成这句
    python scripts/post_to_x.py --part short --send               # 真发：只发短推
    python scripts/post_to_x.py --part all --send --view "……"     # 真发：主贴（带图）+ 回复 + 短推

--part main 是主贴 + 挂在下面的回复；short 是短推，单独发；all 是全部。
key 只从环境变量读：X_API_KEY、X_API_SECRET、X_ACCESS_TOKEN、X_ACCESS_TOKEN_SECRET，不会打印、不会写进任何文件。
发成功的记在 data/posted.csv，同一天同一部分不会重发。
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from common import DATA, OUTPUT, ROOT
from make_post_pack import check, x_len

API = "https://api.x.com/2"
ENV_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
POSTED = DATA / "posted.csv"
POSTED_FIELDS = ["date", "part", "tweet_id", "url", "posted_at"]
MAX_IMAGES = 4
LIMIT = 280       # 拆串推时每条的上限（按 X 计数，中文算 2）
RETRY_WAIT = 3    # 秒。请求失败等一下再试 1 次
NAMES = {"main": "主贴", "reply": "回复", "short": "短推"}
VIEW_LINE = re.compile(r"^我的看法：【需补充[^】]*】[ \t]*$", re.M)

AUTH_HINT = """常见原因：
  1. App 权限要设成 Read and write：developer.x.com → 你的 App → User authentication settings → App permissions
  2. 改完权限要重新生成 Access Token 和 Secret（Keys and tokens 页面），旧 token 还是只读的；生成完更新环境变量
  3. API 余额（credits）为 0 也会失败，去开发者后台看用量和余额
  4. 401 多半是 4 个 key 里有一个填错了或者过期了"""


# ---------- key 和输出 ----------

def _secrets() -> list[str]:
    return [v.strip() for k in ENV_KEYS if len((v := os.environ.get(k, "")).strip()) >= 6]


def redact(text) -> str:
    """任何要打印的字符串都先过一遍：环境变量里的 key 换成 ***。"""
    text = str(text)
    for s in _secrets():
        text = text.replace(s, "***").replace(quote(s, safe=""), "***")  # OAuth 请求头里是转义过的
    return text


def say(*args, file=None):
    print(redact(" ".join(str(a) for a in args)), file=file or sys.stdout)


def load_keys() -> dict[str, str]:
    keys = {k: os.environ.get(k, "").strip() for k in ENV_KEYS}
    lack = [k for k, v in keys.items() if not v]
    if lack:
        raise SystemExit("缺环境变量：" + "、".join(lack) + "\n"
                         "Mac 上写进 ~/.zshrc（export X_API_KEY=...），云端填进环境设置的 Environment variables。"
                         "key 不要写进仓库。")
    return keys


# ---------- X API ----------

class XError(Exception):
    def __init__(self, msg: str, status: int | None = None, body: str = ""):
        super().__init__(msg)
        self.status, self.body = status, body

    @property
    def too_long(self) -> bool:
        return self.status in (400, 403) and bool(
            re.search(r"too long|longer than|shorter|280", self.body, re.I))

    @property
    def duplicate(self) -> bool:
        return self.status == 403 and "duplicate" in self.body.lower()


def x_detail(body: str) -> str:
    """X 的报错 JSON 里挑出能看懂的那句。"""
    try:
        j = json.loads(body)
    except ValueError:
        return body[:300]
    if not isinstance(j, dict):
        return body[:300]
    msgs = [j.get("title"), j.get("detail")]
    msgs += [e.get("message") for e in j.get("errors") or [] if isinstance(e, dict)]
    return "；".join(dict.fromkeys(m for m in msgs if m)) or body[:300]


def api_error(status: int, body: str) -> XError:
    e = XError("", status, body)
    detail = x_detail(body)
    if e.too_long:
        msg = f"X 说太长（HTTP {status}）：{detail}"
    elif e.duplicate:
        msg = (f"X 说内容重复（HTTP {status}）：{detail}\n"
               "可能上一次其实发成功了：去主页看一眼，发了的话把 tweet_id 手动记进 data/posted.csv")
    elif status == 402 or "credits" in body.lower():
        msg = (f"X API 余额用完了（HTTP {status}）：{detail}\n"
               "去 developer.x.com 开发者后台充值 credits 再发。充完第一次发如果报 403，再按下面检查权限：\n"
               f"{AUTH_HINT}")
    elif status in (401, 403):
        msg = f"X 拒绝了请求（HTTP {status}）：{detail}\n{AUTH_HINT}"
    elif status == 429:
        msg = f"限流了（HTTP 429）：{detail}\n过 15 分钟再试"
    else:
        msg = f"X 返回 HTTP {status}：{detail}"
    return XError(msg, status, body)


class XClient:
    """只做两件事：传图、发帖。session 换成假的就能测试，不会真的请求 X。"""

    def __init__(self, session):
        self.s = session

    @classmethod
    def from_env(cls) -> "XClient":
        from requests_oauthlib import OAuth1Session
        k = load_keys()
        return cls(OAuth1Session(k["X_API_KEY"], client_secret=k["X_API_SECRET"],
                                 resource_owner_key=k["X_ACCESS_TOKEN"],
                                 resource_owner_secret=k["X_ACCESS_TOKEN_SECRET"]))

    def _post(self, path: str, payload: dict) -> dict:
        """POST 一次，网络错误 / 5xx / 429 等一下再试 1 次。4xx 不重试（再试也一样）。"""
        err = None
        for attempt in (1, 2):
            try:
                r = self.s.post(API + path, json=payload, timeout=60)
            except (requests.ConnectionError, requests.Timeout) as e:
                err = XError(f"网络错误：{type(e).__name__}: {e}")
            except requests.RequestException as e:
                raise XError(f"请求出错：{type(e).__name__}: {e}") from None
            else:
                if r.status_code < 300:
                    try:
                        return r.json()
                    except ValueError:
                        raise XError(f"X 返回的不是 JSON（HTTP {r.status_code}）：{r.text[:200]}") from None
                err = api_error(r.status_code, r.text)
                if r.status_code < 500 and r.status_code != 429:
                    raise err
            if attempt == 1:
                say(f"  请求失败，{RETRY_WAIT} 秒后重试 1 次：{err}")
                time.sleep(RETRY_WAIT)
        raise err

    def upload_image(self, path: Path) -> str:
        data = base64.b64encode(path.read_bytes()).decode()
        j = self._post("/media/upload", {"media": data, "media_category": "tweet_image"})
        mid = (j.get("data") or {}).get("id") or j.get("media_id_string")
        if not mid:
            raise XError(f"上传 {path.name} 没拿到 media id：{str(j)[:200]}")
        return str(mid)

    def tweet(self, text: str, media_ids: list[str] | None = None, reply_to: str | None = None) -> str:
        body: dict = {"text": text}
        if media_ids:
            body["media"] = {"media_ids": media_ids}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        j = self._post("/tweets", body)
        tid = (j.get("data") or {}).get("id")
        if not tid:
            raise XError(f"发帖没拿到 tweet id：{str(j)[:200]}")
        return str(tid)


# ---------- 拆串推 ----------

# 先按空行拆，一段太长再按换行，一行太长再按句号，一句都太长才按字硬切
SPLITS = [(r"\n\s*\n", "\n\n"), (r"\n", "\n"), (r"(?<=[。！？；!?])", "")]


def _pack(units: list[str], sep: str, limit: int) -> list[str]:
    out: list[str] = []
    for u in units:
        if out and x_len(out[-1] + sep + u) <= limit:
            out[-1] += sep + u
        else:
            out.append(u)
    return out


def split_thread(text: str, limit: int = LIMIT, level: int = 0) -> list[str]:
    """拆成串推，每条按 X 计数不超过 limit。能放一条的段落尽量放一起，不打乱顺序。"""
    text = text.strip()
    if x_len(text) <= limit:
        return [text] if text else []
    if level == len(SPLITS):
        out, cur = [], ""
        for ch in text:
            if cur and x_len(cur + ch) > limit:
                out.append(cur)
                cur = ""
            cur += ch
        return out + [cur]
    pattern, sep = SPLITS[level]
    units = [u for u in re.split(pattern, text) if u.strip()]
    pieces = [p for u in units for p in split_thread(u, limit, level + 1)]
    return _pack(pieces, sep, limit)


# ---------- 发过的记录 ----------

def tweet_url(tid: str) -> str:
    return f"https://x.com/i/status/{tid}"


def posted_ids(day: str) -> dict[str, str]:
    """这一天已经发过的 {part: tweet_id}。串推后面几条是 main_2、main_3……"""
    if not POSTED.exists():
        return {}
    with open(POSTED, newline="", encoding="utf-8-sig") as f:
        return {r["part"]: r["tweet_id"] for r in csv.DictReader(f) if r["date"] == day}


def record(day: str, part: str, tid: str):
    new = not POSTED.exists()
    POSTED.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTED, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=POSTED_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date": day, "part": part, "tweet_id": tid, "url": tweet_url(tid),
                    "posted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


def last_of(done: dict[str, str], part: str) -> str | None:
    """主贴拆成了串推的话，回复挂在最后一条下面。"""
    nums = {1 if k == part else int(k.rsplit("_", 1)[1]): v
            for k, v in done.items() if k == part or re.fullmatch(rf"{part}_\d+", k)}
    return nums[max(nums)] if nums else None


# ---------- 发 ----------

def post_chain(client: XClient, chunks: list[str], part: str, day: str,
               media_ids: list[str] | None = None, reply_to: str | None = None) -> str:
    """一条挂一条发，第一条带图。每发成功一条马上记进 posted.csv。返回最后一条的 id。"""
    for i, text in enumerate(chunks):
        try:
            tid = client.tweet(text, media_ids if i == 0 else None, reply_to)
        except XError:
            if i:
                say(f"  串推发到第 {i + 1}/{len(chunks)} 条失败。前 {i} 条已经发了、记好了；"
                    f"剩下的没发，要手动补：")
                for rest in chunks[i:]:
                    say("  ----\n" + rest)
            raise
        name = part if i == 0 else f"{part}_{i + 1}"
        record(day, name, tid)
        say(f"  {NAMES[part]} {i + 1}/{len(chunks)} 发好了：{tweet_url(tid)}")
        reply_to = tid
    return reply_to


def post_long(client: XClient, text: str, part: str, day: str,
              media_ids: list[str] | None = None, reply_to: str | None = None) -> str:
    """先整条发（Premium 可以超 280）。X 说太长，就按空行拆成串推再发。返回最后一条的 id。"""
    try:
        tid = client.tweet(text, media_ids, reply_to)
    except XError as e:
        if not e.too_long:
            raise
        chunks = split_thread(text)
        say(f"  X 说太长，拆成 {len(chunks)} 条串推再发")
        return post_chain(client, chunks, part, day, media_ids, reply_to)
    record(day, part, tid)
    say(f"  {NAMES[part]} 发好了：{tweet_url(tid)}")
    return tid


def send(client: XClient, day: str, texts: dict[str, str], parts: list[str],
         images: list[Path], done: dict[str, str]):
    last_main = last_of(done, "main")
    if "main" in parts:
        media = [client.upload_image(p) for p in images]
        if media:
            say(f"  传了 {len(media)} 张图")
        last_main = post_long(client, texts["main"], "main", day, media_ids=media)
    if "reply" in parts:
        if not last_main:
            raise XError("找不到主贴的 tweet_id，回复没地方挂")
        post_long(client, texts["reply"], "reply", day, reply_to=last_main)
    if "short" in parts:
        post_long(client, texts["short"], "short", day)


# ---------- 检查 ----------

def load_pack(day: str) -> dict:
    p = OUTPUT / day / "发布包.json"
    if not p.exists():
        raise SystemExit(f"{p} 不存在，先跑 python scripts/make_post_pack.py --date {day}")
    return json.loads(p.read_text(encoding="utf-8"))


def apply_view(main: str, view: str) -> tuple[str, bool]:
    """把「我的看法：【需补充…】」那一行换成 我的看法：<view>。返回 (新主贴, 有没有换到)。"""
    view = " ".join(view.split())
    new, n = VIEW_LINE.subn(lambda _: f"我的看法：{view}", main, count=1)
    return new, bool(n)


def image_paths(pack: dict) -> list[Path]:
    return [p if (p := Path(x)).is_absolute() else ROOT / p for x in pack.get("images") or []]


def show(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def precheck(texts: dict[str, str], parts: list[str], images: list[Path]) -> list[str]:
    """要发的部分过三道检查。返回不能发的原因，空列表 = 可以发。"""
    probs = []
    todo = [t for p in parts for t in re.findall(r"【需补充[^】]*】", texts[p])]
    if todo:
        probs.append("还有【需补充】：" + "、".join(dict.fromkeys(todo)))
    # 规则检查按最终要发的文字重跑（--view 换进去以后），只看这次要发的部分
    names = [NAMES[p] for p in parts]
    issues = [i for i in check({NAMES[k]: v for k, v in texts.items() if v})
              if any(i.startswith(n) for n in names) and "【需补充】" not in i]
    if issues:
        probs.append("规则检查没通过：" + "；".join(issues))
    if "main" in parts:
        if len(images) > MAX_IMAGES:
            probs.append(f"图片有 {len(images)} 张，最多 {MAX_IMAGES} 张")
        lost = [show(p) for p in images if not p.is_file()]
        if lost:
            probs.append("图片文件不存在：" + "、".join(lost))
    return probs


def preview(pack: dict, texts: dict[str, str], parts: list[str], images: list[Path]):
    say(f"{pack.get('date', '')} {pack.get('column', '')}")
    for p in parts:
        n = x_len(texts[p])
        note = f"{n} 字符"
        if p == "reply":
            note += "，挂在主贴下面"
        if n > LIMIT:
            chunks = split_thread(texts[p])
            sizes = "/".join(str(x_len(c)) for c in chunks)
            note += f"，超过 {LIMIT}：先整条发，X 说太长就拆成 {len(chunks)} 条串推（{sizes}）"
        say(f"\n── {NAMES[p]}（{note}）──\n{texts[p]}")
        if p == "main":
            say(f"配图 {len(images)} 张：" + ("、".join(show(i) for i in images) or "无"))
    lack = [k for k in ENV_KEYS if not os.environ.get(k, "").strip()]
    say("\nX key：" + ("4 个环境变量都设置了" if not lack else "缺 " + "、".join(lack)))


def main(argv: list[str] | None = None, client: XClient | None = None) -> int:
    ap = argparse.ArgumentParser(description="把发布包发到 X。不加 --send 只预览。")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--part", choices=["main", "short", "all"], default="all",
                    help="main = 主贴 + 回复；short = 短推；all = 全部")
    ap.add_argument("--send", action="store_true", help="真的发。不加只预览")
    ap.add_argument("--view", help="一句话，替换主贴里「我的看法：【需补充…】」那一行")
    a = ap.parse_args(argv)

    pack = load_pack(a.date)
    texts = {k: (pack.get(k) or "").strip() for k in NAMES}
    done = posted_ids(a.date)
    problems = []

    parts = []
    wanted = (["main", "reply"] if a.part in ("main", "all") else []) + (["short"] if a.part in ("short", "all") else [])
    for p in wanted:
        if p in done:
            say(f"{NAMES[p]} 已经发过：{tweet_url(done[p])}，跳过")
        elif texts[p]:
            parts.append(p)
        elif p != "reply":
            problems.append(f"发布包里没有{NAMES[p]}")

    if a.view is not None and "main" in parts:
        texts["main"], ok = apply_view(texts["main"], a.view)
        if not a.view.strip():
            problems.append("--view 是空的")
        elif not ok:
            problems.append("主贴里没有「我的看法：【需补充…】」这一行，--view 没地方放")

    images = image_paths(pack) if "main" in parts else []
    problems += precheck(texts, parts, images)
    if parts:
        preview(pack, texts, parts, images)

    if problems:
        say("\n✗ 不能发，原因：")
        for i, p in enumerate(problems, 1):
            say(f"  {i}. {p}")
        return 1
    if not parts:
        say("没有要发的。")
        return 0
    if not a.send:
        say("\n✓ 检查全部通过。这是预览，没发。确认没问题再加 --send。")
        return 0

    say("\n开始发……")
    try:
        send(client or XClient.from_env(), a.date, texts, parts, images, done)
    except XError as e:
        say(f"✗ 发推失败：{e}", file=sys.stderr)
        return 1
    except Exception as e:  # 兜底：报错信息也要先去掉 key 再打印
        say(f"✗ 出错了：{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    say(f"✓ 发完了，记录在 {show(POSTED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
