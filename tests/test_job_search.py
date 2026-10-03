"""job_search 的离线测试：岗位内容都是编的测试数据。"""
from job_search import (Job, min_years, needs_grad_degree, parse_ashby, parse_board_list,
                        parse_greenhouse, parse_lever, score)

BOARD_HTML = """
<a href="/job/data-analyst-abc123"><h3>Data Analyst</h3><span>Acme</span><span>·</span>
<span>Remote (US)</span><span>·</span><span>$70k - $90k</span><span>sql</span><span>Remote</span>
<span>junior</span><span>2 weeks ago</span></a>
<a href="/job/senior-ml-engineer-x"><h3>Senior ML Engineer</h3><span>Foo</span><span>London, UK</span>
<span>3 days ago</span></a>
"""


def test_parse_board_list():
    jobs = parse_board_list(BOARD_HTML)
    assert [j.title for j in jobs] == ["Data Analyst", "Senior ML Engineer"]
    assert jobs[0].company == "Acme" and jobs[0].location == "Remote (US)"
    assert jobs[0].salary == "$70k - $90k"
    assert jobs[0].url == "https://aidevboard.com/job/data-analyst-abc123"


def test_parse_ats_feeds():
    gh = parse_greenhouse({"jobs": [{"title": "Analyst", "absolute_url": "https://g/1",
                                     "location": {"name": "Chicago, IL"},
                                     "content": "&lt;p&gt;Use SQL&lt;/p&gt;"}]}, "G")
    assert gh[0].location == "Chicago, IL" and "Use SQL" in gh[0].text
    lv = parse_lever([{"text": "Data Analyst", "hostedUrl": "https://l/1", "workplaceType": "remote",
                       "categories": {"location": "Asia"}, "descriptionPlain": "About",
                       "lists": [{"text": "Requirements", "content": "<li>Python</li>"}]}], "L")
    assert lv[0].location == "Asia (Remote)" and "Python" in lv[0].text
    ab = parse_ashby({"jobs": [{"title": "Quant Analyst", "location": "New York", "isRemote": False,
                                "jobUrl": "https://a/1", "descriptionPlain": "R and SQL"}]}, "A")
    assert ab[0].url == "https://a/1" and ab[0].text == "R and SQL"


def test_min_years_only_counts_experience():
    assert min_years("3+ years of experience in analytics. Founded 10 years ago.") == 3
    assert min_years("1-3 years of experience in research") == 1
    assert min_years("We have been around for 12 years") is None


def test_needs_grad_degree():
    assert needs_grad_degree("Currently pursuing a Masters or PhD degree")
    assert not needs_grad_degree("Bachelors, Masters or PhD in a technical field")


def _job(title, loc="Remote (US)", text=""):
    return score(Job(title, "Co", loc, "u", "test", text=text))


def test_score_tiers():
    good = _job("Data Analyst", text="Recent graduates welcome. 0-1 years of experience. SQL, Python, statistics.")
    assert good.tier == "top" and "招应届生" in good.reasons
    assert _job("Senior Data Analyst").tier == "skip"
    assert _job("Data Analyst", text="5+ years of experience").blockers == ["要 5+ 年经验"]
    assert _job("Data Analyst", text="Must be a U.S. citizen").tier == "no"
    assert _job("Data Analyst", text="We are unable to sponsor visas").tier == "no"
    assert _job("Data Analyst", loc="London, UK").tier == "no"
    assert _job("Data Analyst", loc="Chicago, IL").tier != "no"


def test_scoring_edge_cases():
    assert "用到：excel" not in "；".join(_job("Data Analyst", text="Excellent communication").reasons)
    assert "币圈相关" not in _job("Data Analyst", text="LLM token usage and exchange of ideas").reasons
    assert needs_grad_degree("Pursuing MS or PhD in Computer Science, Statistics, or equivalent field")
    rich = score(Job("Data Scientist", "Co", "Remote (US)", "u", "t", salary="$200k - $250k", text="SQL"))
    assert any("起薪 $200k" in r for r in rich.reasons)


def test_exchange_titles_are_wider():
    ops = Job("Listing Operations Specialist", "Binance", "Asia", "u", "t", focus=True, text="SQL")
    assert score(ops).tier != "skip"
    assert score(Job("Listing Operations Specialist", "Acme", "Asia", "u", "t", text="SQL")).tier == "skip"
    assert score(Job("Senior Compliance Manager", "OKX", "Asia", "u", "t", focus=True)).tier == "skip"
