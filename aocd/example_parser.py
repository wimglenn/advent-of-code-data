from typing import NamedTuple

import bs4


class Example(NamedTuple):
    input_data: str
    answer_a: str = None
    answer_b: str = None
    extra: str = None

    @property
    def answers(self):
        return self.answer_a, self.answer_b


def extract_examples(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    data = soup.pre.text.rstrip("\r\n")
    example = Example(data)
    return [example]
