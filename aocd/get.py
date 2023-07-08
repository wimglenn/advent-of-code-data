import datetime
import os
import re
import traceback
from logging import getLogger

from ._ipykernel import get_ipynb_path
from .exceptions import AocdError
from .exceptions import PuzzleLockedError
from .models import default_user
from .models import Puzzle
from .models import User
from .utils import AOC_TZ
from .utils import blocker


log = getLogger(__name__)


def get_data(session=None, day=None, year=None, block=False):
    """
    Get data for day (1-25) and year (2015+).
    User's session cookie (str) is needed - puzzle inputs differ by user.
    If `block` is True and the puzzle is still locked, will wait until unlock
    before returning data.
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
    try:
        return puzzle.input_data
    except PuzzleLockedError:
        if not block:
            raise
        q = block == "q"
        blocker(quiet=q, until=(year, day))
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
    sep = re.escape(os.sep)
    pattern_path = sep + sep.join([r"20\d\d", r"[0-2]?\d", r".*\.py$"])
    visited = []

    def giveup(msg):
        log.info("introspection failure")
        for fname in visited:
            log.info("stack crawl visited %s", fname)
        return AocdError(msg)

    for frame in traceback.extract_stack():
        filename = frame[0]
        linetxt = frame[-1] or ""
        basename = os.path.basename(filename)
        reasons_to_skip_frame = [
            not re.search(pattern_day, basename),  # no digits in filename
            filename == __file__,  # here
            "importlib" in filename,  # Python 3 import machinery
            "/IPython/" in filename,  # IPython adds a tonne of stack frames
            filename.startswith("<"),  # crap like <decorator-gen-57>
            filename.endswith("ython3"),  # ipython3 alias
            basename.startswith("pydev_ipython_console"),  # PyCharm Python Console
            "aocd" not in linetxt,
            "ipykernel" in filename,
        ]
        visited.append(filename)
        if not any(reasons_to_skip_frame):
            log.debug("stack crawl found %s", filename)
            abspath = os.path.abspath(filename)
            break
        elif "ipykernel" in filename:
            log.debug("stack crawl found %s, attempting to detect an .ipynb", filename)
            try:
                abspath = get_ipynb_path()
            except Exception as err:
                log.debug("failed getting .ipynb path with %s %s", type(err), err)
            else:
                if abspath and re.search(pattern_day, abspath):
                    basename = os.path.basename(abspath)
                    break
        elif re.search(pattern_path, filename):
            year = day = None
            for part in filename.split(os.sep):
                if not part.isdigit():
                    continue
                if len(part) == 4:
                    year = int(part)
                elif 1 <= len(part) <= 2:
                    day = int(part)
            if year is not None and day is not None:
                log.debug("year=%s day=%s filename=%s", year, day, filename)
                return day, year
        log.debug("skipping frame %s", filename)
    else:
        import __main__

        if getattr(__main__, "__file__", "<input>") == "<input>":
            log.debug("running within REPL")
            day = current_day()
            year = most_recent_year()
            return day, year
        log.debug("non-interactive")
        raise giveup("Failed introspection of filename")
    years = {int(year) for year in re.findall(pattern_year, abspath)}
    if len(years) > 1:
        raise giveup("Failed introspection of year")
    year = years.pop() if years else None
    basename_no_years = re.sub(pattern_year, "", basename)
    try:
        [day] = set(re.findall(pattern_day, basename_no_years))
    except ValueError:
        pass
    else:
        assert not day.startswith("0"), "regex pattern_day must prevent any leading 0"
        day = int(day)
        assert 1 <= day <= 25, "regex pattern_day must only match numbers in range 1-25"
        log.debug("year=%s day=%s", year or "?", day)
        return day, year
    log.debug("giving up introspection for %s", abspath)
    raise giveup("Failed introspection of day")
