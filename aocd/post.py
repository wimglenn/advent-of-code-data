import logging
import typing as t

import urllib3

from .get import current_day
from .get import most_recent_year
from .models import default_user
from .models import Puzzle
from .models import User
from ._types import _Part, _Answer


log = logging.getLogger(__name__)


def submit(
    answer: _Answer,
    part: t.Optional[_Part]=None,
    day:t.Optional[int]=None,
    year:t.Optional[int]=None,
    session:t.Optional[str]=None,
    reopen: bool = True,
    quiet: bool = False,
) -> t.Optional[urllib3.BaseHTTPResponse]:
    """
    Submit your answer to adventofcode.com, and print the response to the terminal.
    The only required argument is `answer`, all others can usually be introspected
    from the caller of submit, and whether part b has already been unlocked.
    `answer` can be a string or a number (numbers will be coerced into strings).

    Results are only submitted to the server if the puzzle has not been solved already.
    Additionally, aocd has some internal checks to prevent submitting the same answer
    twice, and to prevent submitting answers which are certain to be incorrect.

    The result of the submission is printed to the terminal. Pass `quiet=True` to
    suppress the printout.

    If it was necessary to POST to adventofcode.com, the HTTP response from the server
    is returned as a `urllib3.HTTPResponse` instance, otherwise the return is None.

    When `reopen` is True (the default), and the puzzle was just solved correctly, this
    function will automatically open/refresh the puzzle page in a new browser tab so
    that you can read the next part quickly. Pass `reopen=False` to suppress this
    feature.
    """
    if session is None:
        user = default_user()
    else:
        user = User(token=session)
    if day is None:
        day = current_day()
    if year is None:
        year = most_recent_year()
    puzzle = Puzzle(year=year, day=day, user=user)
    if part is None:
        # guess if user is submitting for part a or part b,
        # based on whether part a is already solved or not
        answer_a = getattr(puzzle, "answer_a", None)
        log.warning("answer a: %s", answer_a)
        if answer_a is None:
            log.warning("submitting for part a")
            part = "a"
        else:
            log.warning("submitting for part b (part a is already completed)")
            part = "b"
    response = puzzle._submit(value=answer, part=part, reopen=reopen, quiet=quiet)
    return response
