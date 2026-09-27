"""不联网的单元测试。里面的数字都是测试用的，不是真实数据。"""
from common import fmt_pct, fmt_signed
from fetch_daily import _num, parse_farside
from make_post_pack import auto_tag, check, fill, x_len
from predictions import brier

FARSIDE_HTML = """
<table><tr><th></th><th>IBIT</th><th>Total</th></tr>
<tr><td>24 Sep 2026</td><td>10.0</td><td>(12.5)</td></tr>
<tr><td>25 Sep 2026</td><td>1,234.5</td><td>1,300.0</td></tr>
<tr><td>26 Sep 2026</td><td>-</td><td>-</td></tr>
<tr><td>Total</td><td>9</td><td>9</td></tr></table>
"""


def test_brier():
    assert brier(0.3, 0) == 0.09
    assert brier(0.8, 1) == 0.04
    assert brier(0.5, 1) == 0.25


def test_farside_number_formats():
    assert _num("(12.5)") == -12.5
    assert _num("1,234.5") == 1234.5
    assert _num("-") is None


def test_parse_farside_takes_last_filled_day():
    assert parse_farside(FARSIDE_HTML) == ("2026-09-25", 1300.0)


def test_signs():
    assert fmt_pct(1.234) == "+1.23%"
    assert fmt_pct(-2) == "−2.00%"
    assert fmt_pct(0) == "0.00%"
    assert fmt_signed(-5, "-") == "-5.0"


def test_fill_marks_missing():
    assert fill("价格 {BTC_price}", {}) == "价格 【需补充：BTC_price】"


def test_auto_tag_first_mention_only():
    assert auto_tag("$BTC 涨了，BTC 又涨") == "$BTC（我持有） 涨了，BTC 又涨"
    assert auto_tag("看 https://x.com/BTC") == "看 https://x.com/BTC"


def test_x_len():
    assert x_len("abc") == 3
    assert x_len("中文") == 4
    assert x_len("https://example.com/very/long/path") == 23


def test_rules():
    good = {"主贴": "BTC 涨了 5%？\n第二行\n#a #b\n不构成投资建议".replace("BTC", "$BTC（我持有）")}
    assert check(good) == []
    bad = {"主贴": "今天必涨\n#a #b #c\nhttps://x.com"}
    issues = "\n".join(check(bad))
    for word in ("必涨", "3 个话题标签", "不构成投资建议", "链接", "hook"):
        assert word in issues
