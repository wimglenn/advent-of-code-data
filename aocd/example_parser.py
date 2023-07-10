import argparse
import importlib.resources
import json
import logging
import re
import sys
from dataclasses import dataclass
from functools import cache
from itertools import zip_longest
from typing import NamedTuple

import bs4

from aocd.exceptions import ExampleParserError
from aocd.utils import _get_soup


log = logging.getLogger(__name__)


@dataclass
class Page:
    """
    Container of pre-parsed html to be used by example data extraction functions.

    Instances are expected to be initialised with the classmethod factory
    `Page.from_raw(html)` rather than created directly with Page(...).

    Every other attribute of the page is derived from the raw html.
    """
    raw_html: str  # String of the puzzle page html. May or may not have part b unlocked
    soup: bs4.BeautifulSoup  # The raw_html string parsed into a bs4.BeautifulSoup instance
    year: int  # AoC puzzle year (2015+) parsed from html title
    day: int  # AoC puzzle day (1-25) parsed from html title
    article_a: bs4.element.Tag  # The bs4 tag for the first <article> in the page, i.e. part a
    article_b: bs4.element.Tag  # The bs4 tag for the second <article> in the page, i.e. part b. It will be `None` if part b locked
    a_raw: str  # The first <article> html as a string
    b_raw: str  # The second <article> html as a string. Will be `None` if part b locked

    def __repr__(self):
        return f"<Page({self.year}, {self.day}) at {hex(id(self))}{'*' if self.article_b is None else ''}>"

    @classmethod
    def from_raw(cls, html):
        soup = _get_soup(html)
        title_pat = r"^Day (\d{1,2}) - Advent of Code (\d{4})$"
        title_text = soup.title.text
        if (match := re.match(title_pat, title_text)) is None:
            raise ExampleParserError(f"failed to extract year/day from title {title_text!r}")
        day, year = map(int, match.groups())
        articles = soup.find_all('article')
        if len(articles) == 0:
            raise ExampleParserError(f"no <article> found in html")
        elif len(articles) == 1:
            [article_a] = articles
            a_raw = str(article_a)
            article_b = b_raw = None
        elif len(articles) == 2:
            article_a, article_b = articles
            a_raw = str(article_a)
            b_raw = str(article_b)
        else:
            raise ExampleParserError(f"too many <article> found in html")
        page = Page(
            raw_html=html,
            soup=soup,
            year=year,
            day=day,
            article_a=article_a,
            article_b=article_b,
            a_raw=a_raw,
            b_raw=b_raw,
        )
        return page

    def __getattr__(self, name):
        if not name.startswith(("a_", "b_")):
            raise AttributeError(name)
        part, sep, tag = name.partition("_")
        if part == "b" and self.article_b is None:
            # hide part b accessors if part b is not unlocked yet
            raise AttributeError(name)
        if tag not in {"code", "li", "pre"}:
            # only some soup attributes are whitelisted for access
            # these are computed dynamically and cached so that we
            # only pay the cost of parsing for them if/when they are
            # actually used by an example parser
            raise AttributeError(name)
        article = self.article_a if part == "a" else self.article_b
        result = [t.text for t in article.find_all(tag)]
        setattr(self, name, result)  # cache the result
        msg = "cached %s accessors for puzzle %d/%02d part %s page (%d hits)"
        log.debug(msg, tag, self.year, self.day, part, len(result))
        return result


class Example(NamedTuple):
    """
    Tuple of example data, answers, and any extra context needed for a solver.

    A list of these examples is returned by the `Puzzle.examples` property.
    User code should be able to run with the `example.input_data` and is expected
    to produce `example.answer_a` and `example.answer_b`.

    Sometimes examples in the prose need some extra context, such as a fewer
    number of iterations to be used when working with the test data. This may
    be returned as some human-readable string in `example.extra`
    """
    input_data: str
    answer_a: str = None
    answer_b: str = None
    extra: str = None

    @property
    def answers(self):
        return self.answer_a, self.answer_b


def get_actual(year, day):
    examples = []
    from pathlib import Path
    path = Path(f"~/git/advent-of-code-wim/tests/{year}/{day:02d}/").expanduser()
    for p in sorted(path.glob("*.txt")):
        blacklist = "broken", "jwolf", "fizbin", "_wim", "_topaz", "_reddit", "_wim"
        if any(s in p.name for s in blacklist):
            continue
        with p.open() as f:
            lines = list(f)
        input_data = "".join(lines[:-2]).rstrip("\r\n")
        answer_a = lines[-2].split("#")[0].strip()
        answer_b = lines[-1].split("#")[0].strip()
        if answer_a == "-":
            answer_a = None
        if answer_b == "-":
            answer_b = None
        example = Example(input_data, answer_a, answer_b)
        examples.append(example)
    return examples


@cache
def _locators():
    # predetermined locations of code-blocks etc for example data
    resource = importlib.resources.files("aocd") / "examples.json"
    txt = resource.read_text()
    data = json.loads(txt)
    return data


def _trunc(s, maxlen=50):
    # don't print massive strings and mess up the example_parser table rendering
    if s is None or len(s) <= maxlen:
        return s
    return s[:maxlen] + f" ... ({len(s)} bytes)"


def extract_examples(html):
    """
    Takes the puzzle page's raw html (str) and returns a list of `Example` instances.
    """
    page = Page.from_raw(html)
    scope = {
        "soup": page.soup,
        "a": page.article_a,
        "b": page.article_b,
        "p": page,
        "a_code": page.a_code,
        "b_code": page.b_code,
        "a_pre": page.a_pre,
        "b_pre": page.b_pre,
    }
    part_b_locked = page.article_b is None
    result = []
    locators = _locators()
    key = f"{page.year}/{page.day:02d}"
    default = locators["default_locators"]
    for loc in locators.get(key, [default]):
        vals = []
        for k in "input_data", "answer_a", "answer_b", "extra":
            pos = loc.get(k, default[k])
            if k == "extra" and pos is None:
                break
            if k == "answer_b" and (part_b_locked or page.day == 25):
                vals.append(None)
                continue
            try:
                val = eval(pos, scope)
            except Exception:
                val = None
            if val is not None:
                val = val.rstrip("\r\n")
            vals.append(val)
        if vals[0] is not None:
            result.append(Example(*vals))
    return result


def main():
    logging.basicConfig(level=logging.INFO)
    from aocd.models import Puzzle
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        sys.exit(
            f"To use example parser, please install rich:\n"
            f"  {sys.executable} -m pip install rich"
        )
    parser = argparse.ArgumentParser()
    parser.add_argument("-y", "--years", nargs="+", type=int, action="extend")
    args = parser.parse_args()
    years = args.years
    if not years:
        years = range(2015, 2023)
    console = Console()

    wrong = []
    for year in years:
        score = total = 0
        table = Table(title=f"Advent of Code examples for year {year}")
        table.add_column("YYYY/DD", style="cyan")
        table.add_column("eg")
        table.add_column("Example data")
        table.add_column("Part A answer")
        table.add_column("Part B answer")
        table.add_column("Extra")
        missing = Example("")
        for day in range(1, 26):
            p = Puzzle(year, day)
            part_b_locked = len(_get_soup(p._get_prose()).find_all("article")) != 2
            scrapeds = p.examples
            corrects = get_actual(year, day)
            if len(scrapeds) > len(corrects):
                log.warning(f"{year}/{day:02d} scraped {len(scrapeds)} but expected {len(corrects)}")
            for i, (scraped, correct) in enumerate(zip_longest(scrapeds, corrects, fillvalue=missing), start=1):
                row = [""] * 6
                if i == 1:
                    row[0] = f"{year}/{day:02d}"
                row[1] = str(i)
                if part_b_locked:
                    row[1] += "(a)"

                i2 = scraped.input_data == correct.input_data
                i3 = scraped.answer_a == correct.answer_a
                if part_b_locked:
                    i4 = scraped.answer_b is None
                else:
                    i4 = scraped.answer_b == correct.answer_b
                i5 = scraped.extra == correct.extra

                row[2] = "❌✅"[i2] + f" ({len(scraped.input_data or '')} bytes)"
                if not i2:
                    row[2] += f"\n(correct: {len(correct.input_data or '')} bytes)"
                    wrong.append((year, day, i))

                row[3] = "❌✅"[i3] + f" {_trunc(scraped.answer_a)}"
                if not i3:
                    row[3] += f"\n(correct: {correct.answer_a})"
                    wrong.append((year, day, i))

                if day < 25 or scraped.answer_b:
                    row[4] = "❌✅"[i4] + f" {_trunc(scraped.answer_b)}"
                    if not i4:
                        row[4] += f"\n(correct: {correct.answer_b})"
                        wrong.append((year, day, i))
                if day < 25 and part_b_locked and i4:
                    row[4] = "❓"

                if scraped.extra or correct.extra:
                    row[5] = f"{scraped.extra or correct.extra or ''}"

                table.add_row(*row)
        console.print(table)
    wrong = [*{}.fromkeys(wrong)]
    for y, d, i in wrong:
        print(y, d, i)
    sys.exit(f"{len(wrong)} scraped incorrect")
