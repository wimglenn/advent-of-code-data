from __future__ import annotations

from datetime import timedelta
from numbers import Number
from typing import Literal
from typing import TypedDict
from typing import Union

AnswerValue = Union[str, Number]
"""The answer to a puzzle, either a string or a number. Numbers are coerced to a string"""
PuzzlePart = Literal["a", "b"]
"""The part of a given puzzle, a or b"""


class PuzzleStats(TypedDict):
    """Your personal stats for a given puzzle

    See https://adventofcode.com/<year>/leaderboard/self when logged in.
    """

    time: timedelta
    rank: int
    score: int


class Submission(TypedDict):
    """Record of a previous submission made for a given puzzle

    Only applies to answers submitted with aocd.
    """

    part: PuzzlePart
    value: str
    when: str
    message: str
