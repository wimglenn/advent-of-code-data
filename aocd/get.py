from __future__ import print_function

import datetime
import errno
import io
import os
import re
import sys
import time
import traceback
from logging import getLogger
from textwrap import dedent

import requests
from termcolor import cprint

from .exceptions import AocdError
from .utils import ensure_intermediate_dirs
from .utils import AOC_TZ
from .utils import CONF_FNAME
from .utils import MEMO_FNAME
from .utils import URI
from .version import USER_AGENT


log = getLogger(__name__)


RATE_LIMIT = 1  # seconds between consecutive requests


def get_data(session=None, day=None, year=None):
    """
    Get data for day (1-25) and year (>= 2015)
    User's session cookie is needed (puzzle inputs differ by user)
    """
    if session is None:
        session = get_cookie()
    if day is None:
        day = current_day()
        log.info("current day=%s", day)
    if year is None:
        year = most_recent_year()
        log.info("most recent year=%s", year)
    uri = URI.format(year=year, day=day) + "/input"
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    try:
        # use previously received data, if any existing
        with io.open(memo_fname, encoding="utf-8") as f:
            data = f.read()
    except (IOError, OSError) as err:
        if err.errno != errno.ENOENT:
            raise
    else:
        log.info("reusing existing data %s", memo_fname.replace(session, "<token>"))
        return data.rstrip("\r\n")
    log.info("getting data year=%s day=%s", year, day)
    t = time.time()
    delta = t - getattr(get_data, "last_request", t - RATE_LIMIT)
    t_sleep = max(RATE_LIMIT - delta, 0)
    if t_sleep > 0:
        log.warning("You are being rate-limited. Sleeping %d seconds...", t_sleep)
        time.sleep(t_sleep)
    response = requests.get(
        url=uri, cookies={"session": session}, headers={"User-Agent": USER_AGENT}
    )
    get_data.last_request = time.time()
    if not response.ok:
        log.error("got %s status code", response.status_code)
        log.error(response.text)
        raise AocdError("Unexpected response")
    data = response.text
    ensure_intermediate_dirs(memo_fname)
    with open(memo_fname, "w") as f:
        log.info("saving the puzzle input")
        f.write(data)
    return data.rstrip("\r\n")


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
    Raises exception otherwise.
    """
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    if aoc_now.month != 12:
        raise AocdError("current_day is only available in December (EST)")
    day = min(aoc_now.day, 25)
    return day


def get_cookie():
    # export your session id as AOC_SESSION env var
    cookie = os.getenv("AOC_SESSION")
    if cookie:
        return cookie

    # or chuck it in a plaintext file at ~/.config/aocd/token
    try:
        with open(CONF_FNAME) as f:
            cookie = f.read().strip()
    except (IOError, OSError) as err:
        if err.errno != errno.ENOENT:
            raise
    if cookie:
        return cookie

    msg = dedent(
        """\
        ERROR: AoC session ID is needed to get your puzzle data!
        You can find it in your browser cookies after login.
            1) Save the cookie into a text file {}, or
            2) Export the cookie in environment variable AOC_SESSION
        """
    )
    cprint(msg.format(CONF_FNAME), color="red", file=sys.stderr)
    raise AocdError("Missing session ID")


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
    stack = [f[0] for f in traceback.extract_stack()]
    for name in stack:
        if not _skip_frame(name):
            abspath = os.path.abspath(name)
            break
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
    raise AocdError("Failed introspection of day")
