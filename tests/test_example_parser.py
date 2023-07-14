import pytest

from aocd.examples import main
from aocd.examples import Page
from aocd.exceptions import ExampleParserError


fake_prose = """
<title>Day 1 - Advent of Code 1234</title>
<article>
<pre><code>test input data</code></pre>
<code>test answer_a</code>
</article>
<article>
<code>test answer_b</code>
</article>
"""


def test_page_repr(mocker):
    mocker.patch("aocd.examples.hex", return_value="0xcafef00d")
    page_ab = Page.from_raw(html=fake_prose)
    assert repr(page_ab) == f"<Page(1234, 1) at 0xcafef00d>"


def test_page_a_only(mocker):
    mocker.patch("aocd.examples.hex", return_value="0xdeadbeef")
    html_a_only = fake_prose[: fake_prose.rfind("<article>")]
    page_a_only = Page.from_raw(html=html_a_only)
    # The * indicates part b was not unlocked yet
    assert repr(page_a_only) == f"<Page(1234, 1)* at 0xdeadbeef>"
    assert page_a_only.article_b is None
    with pytest.raises(AttributeError("b_code")):
        page_a_only.b_code
    with pytest.raises(AttributeError("wtf")):
        page_a_only.wtf
    with pytest.raises(AttributeError("a_b")):
        page_a_only.a_b


def test_li_drilldown():
    s = "<code>test answer_a</code>"
    html = fake_prose.replace(s, f"<li>{s}</li>")
    page = Page.from_raw(html)
    assert len(page.a_li) == 1
    assert len(page.a_li[0].codes) == 1
    assert page.a_li[0].codes[0] == "test answer_a"


def test_invalid_page_too_many_articles():
    html = fake_prose + "<article></article>"
    err = ExampleParserError("too many <article> found in html")
    with pytest.raises(err):
        Page.from_raw(html=html)


def test_invalid_page_no_articles():
    html = fake_prose.replace("article", "farticle")
    err = ExampleParserError("no <article> found in html")
    with pytest.raises(err):
        Page.from_raw(html=html)


def test_invalid_page_no_title():
    html = fake_prose.replace("Advent", "Advert")
    msg = "failed to extract year/day from title 'Day 1 - Advert of Code 1234'"
    with pytest.raises(ExampleParserError(msg)):
        Page.from_raw(html=html)


def test_aoce(mocker, freezer, pook, capsys):
    pook.get(
        url="https://adventofcode.com:443/2022/day/1",
        response_body=fake_prose,
    )
    freezer.move_to("2022-12-01 12:00:00-0500")
    mocker.patch("sys.argv", ["aoce", "-y", "2022"])
    main()
    out, err = capsys.readouterr()
    assert not err
    assert "✅ (15 bytes)" in out
