"""量化面试题库：每道题的模拟要和公式对上，小红书文案要过检查。不联网，不出图。"""
import unicodedata

import pytest

import build_quant_pack
import make_xhs_notes
from questions import BY_ID, ORDER, QUESTIONS, TOPICS, check_rows

FIELDS = ["id", "topic", "level", "title", "hook", "fx", "q_zh", "q_en", "hint", "answer", "value", "steps",
          "say_en", "trap", "followup", "snippet", "checks"]


def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def test_bank_complete():
    assert len(QUESTIONS) == 30
    assert len(BY_ID) == 30, "题号重复了"
    assert sorted(ORDER) == sorted(BY_ID), "ORDER 要正好包含每道题一次"
    for q in QUESTIONS:
        for f in FIELDS:
            assert q.get(f) not in (None, "", []), f"{q['id']} 缺 {f}"
        assert q["id"][0] in TOPICS
        assert q["level"] in (1, 2, 3)


def test_value_is_first_check():
    for q in QUESTIONS:
        assert q["checks"][0][1] == pytest.approx(q["value"], abs=1e-9), q["id"]
        assert q["checks"][0][2] == "result", f"{q['id']} 第一行要验证 result"


@pytest.mark.parametrize("qid", sorted(BY_ID))
def test_simulation_matches_formula(qid):
    for label, exact, sim, tol in check_rows(BY_ID[qid]):
        if sim is not None:
            assert abs(sim - exact) <= tol, f"{qid} {label}：公式 {exact}，模拟 {sim}"


def test_snippets_fit_card():
    for q in QUESTIONS:
        lines = q["snippet"].splitlines()
        assert lines[0] == "rng = np.random.default_rng(0)", f"{q['id']} 第一行要固定 seed"
        assert len(lines) <= 14, f"{q['id']} 代码超过 14 行，卡片放不下"
        for line in lines:
            assert width(line) <= 52, f"{q['id']} 这行太长：{line}"


def test_note_text_passes_checks():
    for q in QUESTIONS:
        for shop in (False, True):
            title, body = make_xhs_notes.note_text(q, shop)
            assert make_xhs_notes.check_note(title, body) == [], q["id"]
        assert len(q["hook"]) <= 3 and max(make_xhs_notes.em_width(x) for x in q["hook"]) <= 11, q["id"]


def test_check_note_catches_problems():
    problems = "\n".join(make_xhs_notes.check_note("一" * 21, "加我微信 http://a.b 稳赚\n" + "字" * 1000))
    for word in ("标题", "正文", "微信", "http", "稳赚", "AI 辅助"):
        assert word in problems


def test_parse_days():
    assert make_xhs_notes.parse_days("1-3,5") == [1, 2, 3, 5]
    assert make_xhs_notes.parse_days("all") == list(range(1, 31))
    with pytest.raises(SystemExit):
        make_xhs_notes.parse_days("31")


def test_fmt_num():
    assert make_xhs_notes.fmt_num(23.0, 23) == "23"
    assert make_xhs_notes.fmt_num(5.99389, 6.0) == "5.994"
    assert make_xhs_notes.fmt_num(-0.5, -0.5) == "−0.5000"
    assert make_xhs_notes.fmt_num(None, 0.1) == "—"


def test_pack_files_build():
    qs = build_quant_pack.ordered()
    assert [q["id"] for q in qs][:2] == ["P1", "P2"]
    fake = {q["id"]: [(lab, ex, ex, tol) for lab, ex, _, tol in q["checks"]] for q in qs}
    md = build_quant_pack.bank_md(qs, fake)
    assert all(f"## {q['id']} ·" in md for q in qs)
    py = build_quant_pack.verify_py(qs)
    compile(py, "verify.py", "exec")  # 生成的验证代码至少语法没问题
    assert "def q_S6():" in py
