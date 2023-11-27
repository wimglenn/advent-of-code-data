import bs4
import pook as pook_mod
import pytest
from freezegun.api import FrozenDateTimeFactory
from pytest_mock import MockerFixture

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


def test_page_repr(mocker: MockerFixture) -> None:
    mocker.patch("aocd.examples.hex", return_value="0xcafef00d")
    page_ab = Page.from_raw(html=fake_prose)
    assert repr(page_ab) == f"<Page(1234, 1) at 0xcafef00d>"


def test_page_a_only(mocker: MockerFixture) -> None:
    mocker.patch("aocd.examples.hex", return_value="0xdeadbeef")
    html_a_only = fake_prose[: fake_prose.rfind("<article>")]
    page_a_only = Page.from_raw(html=html_a_only)
    # The * indicates part b was not unlocked yet
    assert repr(page_a_only) == f"<Page(1234, 1)* at 0xdeadbeef>"
    assert page_a_only.article_b is None
    with pytest.raises(AttributeError("b_code")): # type: ignore[call-overload] # using pytest-raisin
        page_a_only.b_code
    with pytest.raises(AttributeError("wtf")): # type: ignore[call-overload] # using pytest-raisin
        page_a_only.wtf
    with pytest.raises(AttributeError("a_b")): # type: ignore[call-overload] # using pytest-raisin
        page_a_only.a_b


def test_li_drilldown() -> None:
    s = "<code>test answer_a</code>"
    html = fake_prose.replace(s, f"<li>{s}</li>")
    page = Page.from_raw(html)
    li = page.a_li
    assert len(li) == 1
    li = li[0]
    assert isinstance(li, bs4.Tag)

    # Type checker incorrectly thinks this is an Optional[Tag]. We set it to a list[str].
    codes = li.codes

    assert isinstance(codes, list)
    assert len(codes) == 1
    assert codes[0] == "test answer_a"


def test_invalid_page_too_many_articles() -> None:
    html = fake_prose + "<article></article>"
    err = ExampleParserError("too many <article> found in html")
    with pytest.raises(err): # type: ignore[call-overload] # using pytest-raisin
        Page.from_raw(html=html)


def test_invalid_page_no_articles() -> None:
    html = fake_prose.replace("article", "farticle")
    err = ExampleParserError("no <article> found in html")
    with pytest.raises(err): # type: ignore[call-overload] # using pytest-raisin
        Page.from_raw(html=html)


def test_invalid_page_no_title() -> None:
    html = fake_prose.replace("Advent", "Advert")
    msg = "failed to extract year/day from title 'Day 1 - Advert of Code 1234'"
    with pytest.raises(ExampleParserError(msg)): # type: ignore[call-overload] # using pytest-raisin
        Page.from_raw(html=html)


def test_aoce(mocker: MockerFixture, freezer: FrozenDateTimeFactory, pook: pook_mod, capsys: pytest.CaptureFixture[str]) -> None:
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
