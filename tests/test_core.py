"""不联网的单元测试。里面的数字都是测试用的，不是真实数据。"""
from common import fmt_pct, fmt_signed
import fetch_daily
from fetch_daily import _num, parse_farside
from make_post_pack import auto_tag, check, fill, pick_variant, x_len
from predictions import brier, judge

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


def _fake_prices(table):
    return lambda sym, day: (table[day.isoformat()], "测试")


def test_judge_between_and_up():
    prices = _fake_prices({"2026-10-04": 84000.0, "2026-09-30": 83000.0, "2026-10-31": 82000.0})
    between = {"结算日期": "2026-10-04", "币种": "BTC", "类型": "between", "阈值": 80000, "阈值上限": 88000}
    assert judge(between, prices)[0] == 1
    between["阈值上限"] = 83500
    assert judge(between, prices)[0] == 0
    up = {"结算日期": "2026-10-31", "币种": "BTC", "类型": "up", "参考日期": "2026-09-30"}
    assert judge(up, prices)[0] == 0  # 82000 < 83000
    above = {"结算日期": "2026-10-04", "币种": "BTC", "类型": "above", "阈值": 83999}
    assert judge(above, prices)[0] == 1


def test_manual_etf_takes_latest_on_or_before(tmp_path, monkeypatch):
    from datetime import date
    p = tmp_path / "etf_manual.csv"
    p.write_text("date,symbol,net_flow_usd_m,source_url\n"
                 "2026-09-24,BTC,10,\n2026-09-25,BTC,(bad),\n2026-09-25,ETH,5,u\n2026-09-30,BTC,99,\n",
                 encoding="utf-8")
    monkeypatch.setattr(fetch_daily, "ETF_MANUAL", p)
    assert fetch_daily.manual_etf("BTC", date(2026, 9, 27))[:2] == ("2026-09-24", 10.0)
    assert fetch_daily.manual_etf("ETH", date(2026, 9, 27)) == ("2026-09-25", 5.0, "u")
    assert fetch_daily.manual_etf("ETH", date(2026, 9, 20)) is None


def test_first_issue_variant():
    parts = {"主贴": "累计 A", "主贴·首期": "第 1 期", "回复": "r"}
    assert pick_variant(parts, {}) == {"主贴": "第 1 期", "回复": "r"}
    assert pick_variant(parts, {"pred_count": "3"}) == {"主贴": "累计 A", "回复": "r"}
