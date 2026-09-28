"""post_to_x.py 的测试。全部用假的 X，不会真的请求。里面的数字都是测试用的，不是真实数据。"""
import csv
import json
import re
import sys

import pytest
import requests

import make_post_pack
import post_to_x as px
from make_post_pack import x_len

DAY = "2099-01-05"
KEYS = {"X_API_KEY": "ck_FAKE_consumer_0001", "X_API_SECRET": "cs_FAKE_consumer_secret_0002",
        "X_ACCESS_TOKEN": "123-at_FAKE_token_0003", "X_ACCESS_TOKEN_SECRET": "ats_FAKE_token_secret_0004"}
MAIN = ("$BTC（我持有） 7 天 +5.00%，为什么？\n测试第二行\n\n"
        "我的看法：【需补充：一句用概率或「如果……那么……」表达的判断】\n\n"
        "#比特币 #数据\n不构成投资建议")
REPLY = "数据来源：\nCoinGecko: https://www.coingecko.com/"
SHORT = "$BTC（我持有） 7 天 +5.00%。完整数据表在主页置顶。"
VIEW = "如果 ETF 连续 3 天净流出，那么我会把上涨概率调低。"


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return json.loads(self.text)


TOO_LONG = Resp(400, {"errors": [{"message": "Your Tweet text is too long."}], "title": "Invalid Request",
                      "detail": "One or more parameters to your request was invalid."})
FORBIDDEN = Resp(403, {"title": "Forbidden", "detail": "You are not permitted to perform this action.",
                       "status": 403})


class FakeX:
    """假的 X API：记下每个请求。max_len 设了就把超长的帖子按「太长」拒掉。fail 里的先依次返回/抛出。"""

    def __init__(self, max_len=None, fail=()):
        self.calls, self.n, self.max_len, self.fail = [], 0, max_len, list(fail)

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        if self.fail:
            f = self.fail.pop(0)
            if isinstance(f, Exception):
                raise f
            return f
        self.n += 1
        if url.endswith("/media/upload"):
            return Resp(200, {"data": {"id": f"m{self.n}", "media_key": f"3_m{self.n}"}})
        if self.max_len and x_len(json["text"]) > self.max_len:
            return TOO_LONG
        return Resp(201, {"data": {"id": f"t{self.n}", "text": json["text"]}})

    @property
    def tweets(self):
        return [j for u, j in self.calls if u.endswith("/tweets")]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(px, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(px, "POSTED", tmp_path / "posted.csv")
    monkeypatch.setattr(px, "RETRY_WAIT", 0)
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    return tmp_path


def write_pack(tmp, main=MAIN, reply=REPLY, short=SHORT, n_images=2, extra_images=()):
    d = tmp / "output" / DAY
    d.mkdir(parents=True, exist_ok=True)
    imgs = []
    for i in range(n_images):
        p = d / f"img{i}.png"
        p.write_bytes(b"\x89PNG fake " + bytes([i]))
        imgs.append(str(p))
    pack = {"date": DAY, "column": "周一数据", "main": main, "reply": reply, "short": short,
            "images": imgs + list(extra_images), "checks": {"passed": True, "issues": []}, "todo": []}
    (d / "发布包.json").write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")


def run(fake, *args):
    return px.main(["--date", DAY, *args], client=px.XClient(fake))


def posted_rows(tmp):
    with open(tmp / "posted.csv", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ---------- 发之前的检查 ----------

def test_refuses_when_todo_left(env, capsys):
    write_pack(env)
    fake = FakeX()
    assert run(fake, "--send") == 1
    assert fake.calls == []
    out = capsys.readouterr().out
    assert "不能发" in out and "还有【需补充】" in out
    assert not (env / "posted.csv").exists()


def test_view_fills_the_line_then_sends(env):
    write_pack(env)
    fake = FakeX()
    assert run(fake, "--send", "--view", VIEW) == 0
    main = fake.tweets[0]["text"]
    assert f"我的看法：{VIEW}" in main and "【需补充" not in main


def test_view_without_the_line_refuses(env, capsys):
    write_pack(env, main=MAIN.replace("我的看法：【需补充：一句用概率或「如果……那么……」表达的判断】", "没有看法行"))
    fake = FakeX()
    assert run(fake, "--part", "main", "--send", "--view", VIEW) == 1
    assert fake.calls == [] and "--view 没地方放" in capsys.readouterr().out


def test_rule_check_blocks(env, capsys):
    write_pack(env, main=MAIN.replace("不构成投资建议", ""))
    fake = FakeX()
    assert run(fake, "--send", "--view", VIEW) == 1
    assert fake.calls == [] and "规则检查没通过" in capsys.readouterr().out


def test_images_over_4_or_missing(env, capsys):
    write_pack(env, n_images=5)
    fake = FakeX()
    assert run(fake, "--send", "--view", VIEW) == 1
    assert "最多 4 张" in capsys.readouterr().out
    write_pack(env, n_images=1, extra_images=[str(env / "output" / DAY / "没有这张.png")])
    assert run(fake, "--send", "--view", VIEW) == 1
    out = capsys.readouterr().out
    assert "图片文件不存在" in out and "没有这张.png" in out
    assert fake.calls == []


def test_only_checks_the_part_being_sent(env):
    write_pack(env)  # 主贴还有【需补充】，但只发短推
    fake = FakeX()
    assert run(fake, "--part", "short", "--send") == 0
    assert [t["text"] for t in fake.tweets] == [SHORT]


def test_preview_does_not_send(env, capsys):
    write_pack(env)
    fake = FakeX()
    assert run(fake, "--view", VIEW) == 0
    assert fake.calls == [] and "预览，没发" in capsys.readouterr().out


# ---------- 怎么发 ----------

def test_reply_hangs_under_main_and_short_goes_alone(env):
    write_pack(env)
    fake = FakeX()
    assert run(fake, "--part", "all", "--send", "--view", VIEW) == 0
    uploads = [u for u, _ in fake.calls if u.endswith("/media/upload")]
    assert len(uploads) == 2 and fake.calls[0][1]["media_category"] == "tweet_image"
    main, reply, short = fake.tweets
    assert main["media"]["media_ids"] == ["m1", "m2"] and "reply" not in main
    assert reply["reply"]["in_reply_to_tweet_id"] == "t3"  # t3 = 主贴
    assert "media" not in reply and "https://" in reply["text"] and "https://" not in main["text"]
    assert short == {"text": SHORT}
    rows = posted_rows(env)
    assert [(r["date"], r["part"], r["tweet_id"]) for r in rows] == [(DAY, "main", "t3"), (DAY, "reply", "t4"),
                                                                     (DAY, "short", "t5")]
    assert rows[0]["url"] == "https://x.com/i/status/t3" and rows[0]["posted_at"].endswith("Z")


def test_no_double_post(env, capsys):
    write_pack(env)
    assert run(FakeX(), "--send", "--view", VIEW) == 0
    fake = FakeX()
    assert run(fake, "--send", "--view", VIEW) == 0
    assert fake.calls == []
    assert "已经发过" in capsys.readouterr().out
    assert len(posted_rows(env)) == 3


def test_reply_resumes_under_main_posted_earlier(env):
    """主贴上次发了、回复没发成：再跑一次只补回复，挂在上次的主贴（串推的最后一条）下面。"""
    write_pack(env)
    px.record(DAY, "main", "111")
    px.record(DAY, "main_2", "222")
    fake = FakeX()
    assert run(fake, "--part", "main", "--send") == 0  # 主贴发过了，不用 --view 也不拦
    assert len(fake.calls) == 1 and fake.tweets[0]["reply"]["in_reply_to_tweet_id"] == "222"


def test_long_post_becomes_thread(env):
    paras = [f"第 {i} 段：" + "统计" * 50 + "。" for i in range(1, 6)]  # 每段按 X 计数约 210
    long_main = "$BTC（我持有） 连涨 5 天后第 6 天还涨吗？\n看数据。\n\n" + "\n\n".join(paras) + "\n\n不构成投资建议"
    write_pack(env, main=long_main)
    fake = FakeX(max_len=280)
    assert run(fake, "--send") == 0
    first, *rest = fake.tweets
    assert first["text"] == long_main  # 先整条试
    chunks = [t for t in rest if t["text"] != REPLY and t["text"] != SHORT]
    assert len(chunks) >= 3
    assert all(x_len(c["text"]) <= 280 for c in chunks)
    assert re.sub(r"\s", "", "".join(c["text"] for c in chunks)) == re.sub(r"\s", "", long_main)
    assert chunks[0]["media"]["media_ids"] == ["m1", "m2"]  # 第一条带图，同一批图不重传
    assert all("media" not in c for c in chunks[1:])
    assert len([u for u, _ in fake.calls if u.endswith("/media/upload")]) == 2
    rows = posted_rows(env)
    ids = {r["part"]: r["tweet_id"] for r in rows}
    for i, c in enumerate(chunks[1:], start=2):  # 每条挂在上一条下面
        prev = ids["main"] if i == 2 else ids[f"main_{i - 1}"]
        assert c["reply"]["in_reply_to_tweet_id"] == prev
    reply = next(t for t in fake.tweets if t["text"] == REPLY)
    assert reply["reply"]["in_reply_to_tweet_id"] == ids[f"main_{len(chunks)}"]  # 回复挂在串推最后一条下面
    assert [r["part"] for r in rows] == ["main"] + [f"main_{i}" for i in range(2, len(chunks) + 1)] + ["reply", "short"]


def test_split_thread():
    assert px.split_thread("短的") == ["短的"]
    text = "\n\n".join("段" * 100 for _ in range(4))  # 每段 200
    assert px.split_thread(text) == ["段" * 100] * 4
    text = "\n\n".join("ab" * 30 for _ in range(6))  # 每段 60，四段一条
    assert [len(c.split("\n\n")) for c in px.split_thread(text)] == [4, 2]
    one_line = "字" * 300  # 600，没有标点只能硬切
    chunks = px.split_thread(one_line)
    assert [x_len(c) for c in chunks] == [280, 280, 40] and "".join(chunks) == one_line
    sentences = "一二三四五六七八九十。" * 30  # 按句号切，不切在句子中间
    assert all(c.endswith("。") and x_len(c) <= 280 for c in px.split_thread(sentences))


# ---------- 出错 ----------

def test_retry_once_then_ok(env):
    write_pack(env)
    fake = FakeX(fail=[requests.ConnectionError("断了")])
    assert run(fake, "--part", "short", "--send") == 0
    assert len(fake.calls) == 2 and posted_rows(env)[0]["part"] == "short"


def test_retry_only_once(env, capsys):
    write_pack(env)
    fake = FakeX(fail=[requests.ConnectionError("断了"), requests.Timeout("超时")])
    assert run(fake, "--part", "short", "--send") == 1
    assert len(fake.calls) == 2 and "网络错误" in capsys.readouterr().err
    assert not (env / "posted.csv").exists()


def test_403_explained_and_not_retried(env, capsys):
    write_pack(env)
    fake = FakeX(fail=[FORBIDDEN])
    assert run(fake, "--part", "short", "--send") == 1
    assert len(fake.calls) == 1
    err = capsys.readouterr().err
    for word in ("Read and write", "重新生成", "余额", "HTTP 403"):
        assert word in err


def test_missing_keys_named(env, monkeypatch):
    write_pack(env)
    monkeypatch.delenv("X_ACCESS_TOKEN_SECRET")
    with pytest.raises(SystemExit) as e:
        px.main(["--date", DAY, "--part", "short", "--send"])
    assert "X_ACCESS_TOKEN_SECRET" in str(e.value)


def test_keys_never_in_output(env, monkeypatch, capsys):
    """走真的 OAuth1Session 签名，只把网络层换掉。就算报错信息里带了请求头，打印出来也没有 key。"""
    write_pack(env)
    seen = []

    def fake_send(self, request, **kw):
        auth = request.headers["Authorization"]
        auth = auth.decode() if isinstance(auth, bytes) else auth
        seen.append(auth)
        if len(seen) == 1:
            raise requests.ConnectionError(f"连接断了，请求头 {auth}")
        r = requests.Response()
        r.status_code, r.request, r.url = 401, request, request.url
        r._content = f'{{"title": "Unauthorized", "detail": "Unauthorized {auth}"}}'.encode()
        return r

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    assert px.main(["--date", DAY, "--part", "short", "--send"]) == 1
    assert len(seen) == 2 and KEYS["X_API_KEY"] in seen[0] and KEYS["X_ACCESS_TOKEN"] in seen[0]  # 请求头里确实有
    out = capsys.readouterr()
    text = out.out + out.err
    assert "***" in text and "HTTP 401" in text
    files = "".join(p.read_text(encoding="utf-8") for p in env.rglob("*") if p.suffix in (".csv", ".json", ".md"))
    for v in KEYS.values():
        assert v not in text and v not in files


def test_redact(monkeypatch):
    monkeypatch.setenv("X_API_SECRET", "s3cr+t/key==")
    assert px.redact("a s3cr+t/key== b s3cr%2Bt%2Fkey%3D%3D") == "a *** b ***"  # 原样和转义后的都换掉


# ---------- make_post_pack 出的 JSON ----------

def test_post_pack_writes_json_that_post_to_x_reads(env, monkeypatch, capsys):
    monkeypatch.setattr(make_post_pack, "OUTPUT", env / "output")
    monkeypatch.setattr(sys, "argv", ["make_post_pack.py", "--date", DAY, "--column", "周一数据"])
    make_post_pack.main()  # 2099 年没有数据，数字都会是【需补充】
    pack = json.loads((env / "output" / DAY / "发布包.json").read_text(encoding="utf-8"))
    assert set(pack) >= {"main", "reply", "short", "images", "checks", "todo"}
    assert pack["column"] == "周一数据" and pack["images"] == []
    assert pack["checks"]["passed"] is False and pack["todo"]
    assert "我的看法：【需补充" in pack["main"]
    fake = FakeX()
    assert run(fake, "--send", "--view", VIEW) == 1  # 数字还缺，照样拦住
    assert fake.calls == []


def test_pack_json_image_paths():
    from datetime import date
    from common import ROOT
    j = make_post_pack.pack_json(date(2099, 1, 5), "周一数据", {"主贴": "m"}, [ROOT / "output/2099-01-05/price.png"],
                                 [], [])
    assert j["images"] == ["output/2099-01-05/price.png"] and j["checks"] == {"passed": True, "issues": []}
    assert j["reply"] == "" and j["short"] == ""
