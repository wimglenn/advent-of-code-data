import argparse
import importlib.resources
import json
import logging
import sys
from functools import cache
from itertools import zip_longest
from typing import NamedTuple

from aocd.utils import _get_soup


class Example(NamedTuple):
    input_data: str
    answer_a: str = None
    answer_b: str = None
    extra: str = None

    @property
    def answers(self):
        return self.answer_a, self.answer_b


def extract_examples_old(html, year=None, day=None):
    soup = _get_soup(html)
    if soup.pre is None:
        return []
    data = soup.pre.text.rstrip("\r\n")
    articles = soup.find_all("article")
    if len(articles) == 1:
        [part_a_article] = articles
        part_b_article = None
    elif len(articles) == 2:
        part_a_article, part_b_article = articles
    else:
        return [Example(data)]
    answer_a = part_a_article.find_all("code")[-1].text
    if part_b_article is not None:
        answer_b = part_b_article.find_all("code")[-1].text
    else:
        answer_b = None
    if "\n" in answer_a:
        answer_a = None
    if "\n" in answer_b:
        answer_b = None
    example = Example(data, answer_a=answer_a, answer_b=answer_b)
    return [example]


def get_actual(year, day):
    examples = []
    from pathlib import Path
    path = Path(f"~/git/advent-of-code-wim/tests/{year}/{day:02d}/").expanduser()
    for p in sorted(path.glob("*.txt")):
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
    resource = importlib.resources.files("aocd") / "examples.json"
    txt = resource.read_text()
    data = json.loads(txt)
    return data


def _trunc(s, maxlen=50):
    if s is None or len(s) <= maxlen:
        return s
    return s[:maxlen] + f" ... ({len(s)} bytes)"


def extract_examples(html, year, day):
    soup = _get_soup(html)
    scope = {"soup": soup}
    part_b_locked = len(soup.find_all("article")) != 2
    result = []
    locators = _locators()
    key = f"{year}/{day:02d}"
    default = locators["default_locators"]
    for loc in locators.get(key, [default]):
        vals = []
        for k in "input_data", "answer_a", "answer_b", "extra":
            pos = loc.get(k, default[k])
            if k == "extra" and pos is None:
                break
            if k == "answer_b" and (part_b_locked or day == 25):
                vals.append(None)
                continue
            val = eval(pos, scope)
            if val is not None:
                val = val.rstrip("\r\n")
            vals.append(val)
        result.append(Example(*vals))
    return result


# TODO: delete this helper
def fc(s, val, a=None):
    s_orig = s
    if a is not None:
        s = s.find_all('article')[a]
    code_blocks = s.find_all('code')
    n = len(code_blocks)
    [i] = [i for i, c in enumerate(code_blocks) if c.text == str(val)]
    i_ = i - n
    if a is not None:
        assert s_orig.find_all('article')[a].find_all('code')[i].text == str(val)
        print(f"soup.find_all('article')[{a}].find_all('code')[{i}].text")
        assert s_orig.find_all('article')[a].find_all('code')[i_].text == str(val)
        print(f"soup.find_all('article')[{a}].find_all('code')[{i_}].text")
    else:
        assert s.find_all('code')[i].text == str(val)
        assert s is s_orig
        print(f"soup.find_all('code')[{i}].text")
        if a == 0:
            assert s_orig.find_all('article')[a].find_all('code')[i].text == str(val)
            print(f"soup.find_all('article')[{a}].find_all('code')[{i}].text")


if __name__ == "__main__":
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

                row[3] = "❌✅"[i3] + f" {_trunc(scraped.answer_a)}"
                if not i3:
                    row[3] += f"\n(correct: {correct.answer_a})"

                if day < 25 or scraped.answer_b:
                    row[4] = "❌✅"[i4] + f" {_trunc(scraped.answer_b)}"
                    if not i4:
                        row[4] += f"\n(correct: {correct.answer_b})"
                if day < 25 and part_b_locked and i4:
                    row[4] = "❓"

                if scraped.extra or correct.extra:
                    row[5] = "❌✅"[i5] + f" {scraped.extra}"
                    if not i5:
                        row[5] = f"\n(correct: {correct.extra})"

                table.add_row(*row)
        console.print(table)
