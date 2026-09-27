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


def test_defillama_parsers():
    day = 86400
    stable = [{"date": str(1_000_000 + i * day), "totalCirculatingUSD": {"peggedUSD": 100.0 + i, "peggedEUR": 1.0}}
              for i in range(8)]
    d, v, chg = fetch_daily.parse_stablecoins(stable)
    assert v == 108.0 and round(chg, 4) == round((108 / 101 - 1) * 100, 4)
    d, v, chg = fetch_daily.parse_tvl([{"date": 1_000_000, "tvl": 50.0}, {"date": 1_000_000 + 3 * day, "tvl": 60.0}])
    assert v == 60.0 and chg is None  # 不够 7 天，不算变化


def test_fred_parser_skips_dots():
    obs = [{"date": "2026-09-16", "value": "4.80"}, {"date": "2026-09-18", "value": "4.90"},
           {"date": "2026-09-23", "value": "5.03"}, {"date": "2026-09-25", "value": "."}]
    assert fetch_daily.parse_fred(obs) == ("2026-09-23", 5.03, 0.23)


def test_polymarket_parser():
    m = {"outcomes": '["Yes", "No"]', "outcomePrices": '["0.62", "0.38"]', "endDate": "2026-10-31T12:00:00Z"}
    assert fetch_daily.parse_polymarket(m) == (0.62, "2026-10-31")
    m = {"outcomes": ["No", "Yes"], "outcomePrices": ["0.7", "0.3"]}
    assert fetch_daily.parse_polymarket(m)[0] == 0.3


def test_fees_ref_date_is_last_full_day():
    assert fetch_daily.fees_ref_date({"totalDataChart": [[1790208000, 5], [1790294400, 7]]}) == "2026-09-25"
    assert fetch_daily.fees_ref_date({}) == ""


def test_polymarket_event_pick_and_link():
    ms = [{"groupItemThreshold": "2", "volumeNum": 10}, {"groupItemThreshold": "0", "volumeNum": 30},
          {"groupItemThreshold": "1", "volumeNum": 20}, {"groupItemThreshold": "3", "volumeNum": 99, "closed": True}]
    assert [m["groupItemThreshold"] for m in fetch_daily.pick_event_markets(ms, n=2)] == ["0", "1"]
    assert fetch_daily.pm_page({"events": [{"slug": "ev"}]}, "mk") == "https://polymarket.com/event/ev"
    assert fetch_daily.pm_page({}, "mk") == "https://polymarket.com/event/mk"


def test_data_vars_from_csv(tmp_path, monkeypatch):
    import common
    from make_post_pack import data_vars
    rows = [fetch_daily.row("defi", "HYPE", "holders_revenue_30d", 58710000, "USD", "DefiLlama", "u"),
            fetch_daily.row("defi", "ALL", "stablecoin", 3.0e11, "USD", "DefiLlama", "u", ref_date="2026-09-26"),
            fetch_daily.row("defi", "ALL", "stablecoin_chg_7d", 0.5, "%", "DefiLlama", "u"),
            fetch_daily.row("macro", "us5y", "value", 5.03, "%", "FRED", "u", ref_date="2026-09-23"),
            fetch_daily.row("macro", "us5y", "chg_1w", 0.23, "pp", "FRED", "u"),
            fetch_daily.row("polymarket", "BTC 10 月收涨", "yes_prob", 58.0, "%", "Polymarket", "u")]
    import csv
    p = tmp_path / "2099-01-01.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fetch_daily.FIELDS); w.writeheader(); w.writerows(rows)
    monkeypatch.setattr(common, "DATA", tmp_path)
    v = data_vars(common.Daily("2099-01-01"))
    assert v["HYPE_holders_revenue_30d"] == "$58.71M"
    assert v["stable_mcap"] == "$300.00B" and v["stable_7d"] == "+0.50%"
    assert v["us5y"] == "5.03%" and v["us5y_chg_1w"] == "+0.23 个百分点"
    assert "BTC 10 月收涨：市场给 58%" in v["pm_block"]
