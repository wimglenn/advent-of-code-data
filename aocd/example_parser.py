from typing import NamedTuple

import bs4


class Example(NamedTuple):
    data: str
    part_a_answer: str = None
    part_b_answer: str = None
    extra: str = None


def extract_examples(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    data = soup.pre.text.rstrip("\r\n")
    example = Example(data)
    return [example]


