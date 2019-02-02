# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import os
import re
import traceback
from logging import getLogger

from .exceptions import AocdError
from .models import default_user
from .models import Puzzle
from .models import User
from .utils import AOC_TZ


log = getLogger(__name__)


def get_data(session=None, day=None, year=None):
    """
    Get data for day (1-25) and year (>= 2015)
    User's session cookie is needed (puzzle inputs differ by user)
    """
    if session is None:
        user = default_user()
    else:
        user = User(token=session)
    if day is None:
        day = current_day()
        log.info("current day=%s", day)
    if year is None:
        year = most_recent_year()
        log.info("most recent year=%s", year)
    puzzle = Puzzle(year=year, day=day, user=user)
    return puzzle.input_data


def most_recent_year():
    """
    This year, if it's December.
    The most recent year, otherwise.
    Note: Advent of Code started in 2015
    """
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    year = aoc_now.year
    if aoc_now.month < 12:
        year -= 1
    if year < 2015:
        raise AocdError("Time travel not supported yet")
    return year


def current_day():
    """
    Most recent day, if it's during the Advent of Code. Happy Holidays!
    Day 1 is assumed, otherwise.
    """
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    if aoc_now.month != 12:
        log.warning("current_day is only available in December (EST)")
        return 1
    day = min(aoc_now.day, 25)
    return day


def _skip_frame(name):
    basename = os.path.basename(name)
    skip = any(
        [
            name == __file__,
            "importlib" in name,  # Python 3 import machinery
            "/IPython/" in name,  # ipython adds a tonne of stack frames
            name.startswith("<"),  # crap like <decorator-gen-57>
            name.endswith("ython3"),  # ipython3 alias
            not re.search(r"[1-9]", basename),  # no digits in filename
        ]
    )
    return skip


def get_day_and_year():
    """
    Returns tuple (day, year).

    Here be dragons!

    The correct date is determined with introspection of the call stack, first
    finding the filename of the module from which ``aocd`` was imported.

    This means your filenames should be something sensible, which identify the
    day and year unambiguously. The examples below should all parse correctly,
    because they have unique digits in the file path that are recognisable as
    AoC years (2015+) or days (1-25).

    A filename like ``problem_one.py`` will not work, so don't do that. If you
    don't like weird frame hacks, just use the ``aocd.get_data()`` function
    directly instead and have a nice day!
    """
    pattern_year = r"201[5-9]|202[0-9]"
    pattern_day = r"2[0-5]|1[0-9]|[1-9]"
    pattern_site = r"[Pp]ython\d\.?\d.site-packages."
    stack = [f[0] for f in traceback.extract_stack()]
    for name in stack:
        if not _skip_frame(name):
            abspath = os.path.abspath(name)
            break
        log.debug("skipping frame %s", name)
    else:
        import __main__

        try:
            __main__.__file__
        except AttributeError:
            log.debug("running within REPL")
            day = current_day()
            year = most_recent_year()
            return day, year
        else:
            log.debug("non-interactive")
            raise AocdError("Failed introspection of filename")
    years = {int(year) for year in re.findall(pattern_year, abspath)}
    if len(years) > 1:
        raise AocdError("Failed introspection of year")
    year = years.pop() if years else None
    fname = re.sub(pattern_year, "", abspath)
    fname = re.sub(pattern_site, "", fname)
    try:
        [day] = set(re.findall(pattern_day, fname))
    except ValueError:
        pass
    else:
        assert not day.startswith("0"), "regex pattern_day must prevent any leading 0"
        day = int(day)
        assert 1 <= day <= 25, "regex pattern_day must only match numbers in range 1-25"
        log.debug("year=%d day=%d", year, day)
        return day, year
    log.debug("giving up introspection for %s", abspath)
    raise AocdError("Failed introspection of day")
