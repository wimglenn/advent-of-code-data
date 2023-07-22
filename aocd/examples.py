import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from itertools import zip_longest
from typing import NamedTuple

import bs4

from aocd import models
from aocd.exceptions import ExampleParserError
from aocd.utils import _get_soup
from aocd.utils import AOC_TZ
from aocd.utils import get_plugins


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
        part_a_only = "*" if self.article_b is None else ""
        return f"<Page({self.year}, {self.day}){part_a_only} at {hex(id(self))}>"

    @classmethod
    def from_raw(cls, html):
        soup = _get_soup(html)
        title_pat = r"^Day (\d{1,2}) - Advent of Code (\d{4})$"
        title_text = soup.title.text
        if (match := re.match(title_pat, title_text)) is None:
            msg = f"failed to extract year/day from title {title_text!r}"
            raise ExampleParserError(msg)
        day, year = map(int, match.groups())
        articles = soup.find_all("article")
        if len(articles) == 0:
            raise ExampleParserError("no <article> found in html")
        elif len(articles) == 1:
            [article_a] = articles
            a_raw = str(article_a)
            article_b = b_raw = None
        elif len(articles) == 2:
            article_a, article_b = articles
            a_raw = str(article_a)
            b_raw = str(article_b)
        else:
            raise ExampleParserError("too many <article> found in html")
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
        if tag not in {"code", "li", "pre", "em"}:
            # only some soup attributes are whitelisted for access
            # these are computed dynamically and cached so that we
            # only pay the cost of parsing for them if/when they are
            # actually used by an example parser
            raise AttributeError(name)
        article = self.article_a if part == "a" else self.article_b
        if tag == "li":
            # list items usually need further drill-down
            result = article.find_all("li")
            for li in result:
                li.codes = [code.text for code in li.find_all("code")]
        else:
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


def _trunc(s, maxlen=50):
    # don't print massive strings and mess up the table rendering
    if s is None or len(s) <= maxlen:
        return s
    return s[:maxlen] + f" ... ({len(s)} bytes)"


def _get_unique_real_inputs(year, day):
    # these are passed to example parsers, in case the shape/content of the real
    # input(s) is in some way useful for extracting the example input(s). it is
    # not currently used by the default example parser implementation.
    path = models.AOCD_DATA_DIR
    paths = path.glob(f"*/{year}_{day:02d}_input.txt")
    strs = [p.read_text(encoding="utf-8") for p in paths]
    return list({}.fromkeys(strs))


def main():
    """
    Summarize an example parser's results with historical puzzles' prose, and
    compare the performance against a reference implementation
    """
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        sys.exit(
            f"To use example parser, please install rich:\n"
            f"  {sys.executable} -m pip install rich"
        )
    eps = get_plugins(group="adventofcode.examples")
    plugins = {ep.name: ep for ep in eps}
    aoc_now = datetime.now(tz=AOC_TZ)
    all_years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        "--example-parser",
        choices=list(plugins),
        default="reference",
        help="plugin to use for example extraction testing (default: %(default)s)",
    )
    parser.add_argument(
        "-y",
        "--years",
        metavar="2015+",
        nargs="+",
        help="years to run the parser against (can specify multiple)",
        choices=all_years,
        type=int,
        action="extend",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="increased logging (-v INFO, -vv DEBUG)",
    )
    args = parser.parse_args()
    if args.verbose is None:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)
    years = args.years
    if not years:
        years = all_years
    if not plugins:
        print(
            "There are no plugins available. Install some package(s) "
            "with a registered 'adventofcode.examples' entry-point.\n"
            "See https://github.com/wimglenn/aocd-example-parser "
            "for a sample plugin package structure.",
            file=sys.stderr,
        )
        sys.exit(1)
    plugin = plugins[args.example_parser].load()
    console = Console()
    parser_wants_real_datas = getattr(plugin, "uses_real_datas", True)

    wrong = count = 0
    for year in years:
        table = Table(title=f"Advent of Code examples for year {year}")
        table.add_column("YYYY/DD", style="cyan")
        table.add_column("count")
        table.add_column("eg")
        table.add_column("Example data")
        table.add_column("Part A answer")
        table.add_column("Part B answer")
        table.add_column("Extra")
        missing = Example("")
        for day in range(1, 26):
            puzzle = models.Puzzle(year, day)
            if datetime.now(tz=AOC_TZ) < puzzle.unlock_time(local=False):
                break
            page = Page.from_raw(html=puzzle._get_prose())
            part_b_locked = page.article_b is None
            if parser_wants_real_datas:
                real_inputs = _get_unique_real_inputs(year, day)
            else:
                real_inputs = []
            scrapeds = plugin(page, real_inputs)
            corrects = puzzle.examples

            count_scraped = len(scrapeds)
            count_correct = len(corrects)
            i1 = count_scraped == count_correct

            if len(scrapeds) != len(corrects):
                msg = f"{year}/{day:02d} scraped {len(scrapeds)} but expected {len(corrects)}"
                log.info(msg)

            rows = enumerate(zip_longest(scrapeds, corrects, fillvalue=missing), 1)
            for i, (scraped, correct) in rows:
                inc = correct != missing
                row = [""] * 7
                if i == 1:
                    row[0] = f"{year}/{day:02d}"
                    row[1] = "❌✅"[i1] + f" {count_scraped}"
                    count += inc
                    if not i1:
                        row[1] += f"\n(correct: {count_correct})"
                        wrong += inc

                row[2] = str(i)
                if part_b_locked and day != 25:
                    row[2] += "(a)"
                i3 = scraped.input_data == correct.input_data
                i4 = scraped.answer_a == correct.answer_a
                if part_b_locked:
                    i5 = scraped.answer_b is None
                else:
                    i5 = scraped.answer_b == correct.answer_b

                row[3] = "❌✅"[i3] + f" ({len(scraped.input_data or '')} bytes)"
                count += inc
                if not i3:
                    row[3] += f"\n(correct: {len(correct.input_data or '')} bytes)"
                    wrong += inc

                row[4] = "❌✅"[i4] + f" {_trunc(scraped.answer_a)}"
                count += inc
                if not i4:
                    row[4] += f"\n(correct: {correct.answer_a})"
                    wrong += inc

                if day < 25 and part_b_locked and i5:
                    row[5] = "❓"
                elif day < 25 or scraped.answer_b:
                    row[5] = "❌✅"[i5] + f" {_trunc(scraped.answer_b)}"
                    count += inc
                    if not i5:
                        row[5] += f"\n(correct: {correct.answer_b})"
                        wrong += inc

                if scraped.extra or correct.extra:
                    row[6] = f"{scraped.extra or correct.extra or ''}"

                table.add_row(*row)
        console.print(table)
    score = count - wrong
    print(f"plugin {args.example_parser!r} scored {score}/{count} ({score/count:.1%})")
