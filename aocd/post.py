# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from .get import current_day
from .get import most_recent_year
from .models import default_user
from .models import Puzzle
from .models import User


log = logging.getLogger(__name__)


def submit(
    answer, part=None, day=None, year=None, session=None, reopen=True, quiet=False
):
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
        # guess if user is submitting for part a or part b
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
