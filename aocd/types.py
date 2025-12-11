from __future__ import annotations

import sys
from datetime import timedelta
from typing import Any
from typing import Literal
from typing import TypedDict

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired


AnswerValue = Any
"""The answer to a puzzle, either a string or a number. Numbers are coerced to a string"""
PuzzlePart = Literal["a", "b"]
"""The part of a given puzzle, a or b"""


class PuzzleStats(TypedDict):
    """Your personal stats for a given puzzle

    See https://adventofcode.com/<year>/leaderboard/self when logged in.

    Since 2025, "rank" and "score" are no longer provided.
    """

    time: timedelta
    rank: NotRequired[int]
    score: NotRequired[int]


class Submission(TypedDict):
    """Record of a previous submission made for a given puzzle

    Only applies to answers submitted with aocd.
    """

    part: PuzzlePart
    value: str
    when: str
    message: str
