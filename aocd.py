from __future__ import print_function

import argparse
import datetime
import errno
import io
import os
import re
import sys
import time
import traceback
import webbrowser
from functools import partial
from logging import getLogger
from textwrap import dedent

import bs4
import pytz
import requests
from termcolor import cprint


__version__ = "0.7.0"
__all__ = [
    "data", "get_data", "get_answer", "main", "submit", "__version__",
    "AocdError", "PuzzleUnsolvedError", "AOC_TZ", "current_day",
    "most_recent_year", "get_cookie",
]


log = getLogger(__name__)


URI = "https://adventofcode.com/{year}/day/{day}"
AOC_TZ = pytz.timezone("America/New_York")
CONF_FNAME = os.path.expanduser("~/.config/aocd/token")
MEMO_FNAME = os.path.expanduser("~/.config/aocd/{session}/{year}/{day}.txt")
RATE_LIMIT = 1  # seconds between consecutive requests
USER_AGENT = "aocd.py/v{}".format(__version__)


class AocdError(Exception):
    pass


class PuzzleUnsolvedError(AocdError):
    pass


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
        cprint("You are being rate-limited.", color="red")
        cprint("Sleeping {} seconds...".format(t_sleep))
        time.sleep(t_sleep)
        cprint("Done.")
    response = requests.get(
        url=uri, cookies={"session": session}, headers={"User-Agent": USER_AGENT}
    )
    get_data.last_request = time.time()
    if not response.ok:
        log.error("got %s status code", response.status_code)
        log.error(response.text)
        raise AocdError("Unexpected response")
    data = response.text
    _ensure_intermediate_dirs(memo_fname)
    with open(memo_fname, "w") as f:
        log.info("caching this data")
        f.write(data)
    return data.rstrip("\r\n")


def get_answer(day, year, session=None, level=1):
    """
    Get correct answer for day (1-25), year (>= 2015), and level (1 or 2)
    User's session cookie is needed (puzzle answers differ by user)
    Note: Answers are only revealed after a correct submission. If you
    have not already solved the puzzle, this AocdError will be raised.
    """
    if session is None:
        session = get_cookie()
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {1: "a", 2: "b"}[int(level)]
    answer_fname = memo_fname.replace(".txt", "{}_answer.txt".format(part))
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            return f.read().strip()
    # check question page for already solved answers
    uri = URI.format(year=year, day=day)
    response = requests.get(
        uri,
        cookies={"session": session},
        headers={"User-Agent": USER_AGENT},
    )
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    response.raise_for_status()
    paras = [p for p in soup.find_all('p') if p.text.startswith("Your puzzle answer was")]
    if paras:
        parta_correct_answer = paras[0].code.text
        save_correct_answer(answer=parta_correct_answer, day=day, year=year, level=1, session=session)
        if len(paras) > 1:
            _p1, p2 = paras
            partb_correct_answer = p2.code.text
            save_correct_answer(answer=partb_correct_answer, day=day, year=year, level=2, session=session)
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            return f.read().strip()
    msg = "Answer {}-{}{} is not available".format(year, day, part)
    raise PuzzleUnsolvedError(msg)


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

    # heck, you can just paste it in directly here if you want:
    cookie = ""
    if cookie:  # pragma: no cover
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


def _ensure_intermediate_dirs(fname):
    parent = os.path.dirname(fname)
    try:
        os.makedirs(parent, exist_ok=True)
    except TypeError:
        # exist_ok not avail on Python 2
        try:
            os.makedirs(parent)
        except (IOError, OSError) as err:
            if err.errno != errno.EEXIST:
                raise


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
    pattern_year = r"201[5-9]|202[0-9]"
    pattern_day = r"2[0-5]|1[0-9]|[1-9]"
    stack = [f[0] for f in traceback.extract_stack()]
    for name in stack:
        if not _skip_frame(name):
            abspath = os.path.abspath(name)
            break
    else:
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


def save_correct_answer(answer, day, year, level, session):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_answer.txt".format(part))
    _ensure_intermediate_dirs(answer_fname)
    with open(answer_fname, "w") as f:
        log.info("caching this data")
        f.write(str(answer).strip())


def save_incorrect_answer(answer, day, year, level, session, extra):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_bad_answers.txt".format(part))
    _ensure_intermediate_dirs(answer_fname)
    with open(answer_fname, "a") as f:
        log.info("caching this data")
        f.write(str(answer).strip() + " " + extra.replace("\n", " ") + "\n")


def get_incorrect_answers(day, year, level, session):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_bad_answers.txt".format(part))
    result = {}
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            for line in f:
                answer, _sep, extra = line.strip().partition(" ")
                result[answer] = extra
    return result


def submit(answer, level=None, day=None, year=None, session=None, reopen=True, quiet=False):
    if level not in {1, 2, "1", "2", None}:
        raise AocdError("level must be 1 or 2")
    if session is None:
        session = get_cookie()
    if day is None:
        day = current_day()
    if year is None:
        year = most_recent_year()
    if level is None:
        # guess if user is submitting for part a or part b
        try:
            get_answer(day=day, year=year, session=session, level=1)
        except PuzzleUnsolvedError:
            log.debug("submitting for part a")
            level = 1
        else:
            log.debug("submitting for part b (part a is already completed)")
            level = 2
    bad_guesses = get_incorrect_answers(day=day, year=year, level=level, session=session)
    if str(answer) in bad_guesses:
        if not quiet:
            msg = "aocd will not submit that answer again. You've previously guessed {} and the server responded:"
            print(msg.format(answer))
            cprint(bad_guesses[str(answer)], "red")
        return
    uri = URI.format(year=year, day=day) + "/answer"
    log.info("posting to %s", uri)
    response = requests.post(
        uri,
        cookies={"session": session},
        headers={"User-Agent": USER_AGENT},
        data={"level": level, "answer": answer},
    )
    if not response.ok:
        log.error("got %s status code", response.status_code)
        log.error(response.text)
        raise AocdError("Non-200 response for POST: {}".format(response))
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    message = soup.article.text
    color = None
    if "That's the right answer" in message:
        color = "green"
        if reopen:
            webbrowser.open(response.url)  # So you can read part B on the website...
        save_correct_answer(answer=answer, day=day, year=year, level=level, session=session)
    elif "Did you already complete it" in message:
        color = "yellow"
    elif "That's not the right answer" in message:
        color = "red"
        you_guessed = soup.article.span.code.text
        log.warning("wrong answer %s", you_guessed)
        save_incorrect_answer(answer=answer, day=day, year=year, level=level, session=session, extra=soup.article.text)
    elif "You gave an answer too recently" in message:
        wait_pattern = r"You have (?:(\d+)m )?(\d+)s left to wait"
        try:
            [(minutes, seconds)] = re.findall(wait_pattern, message)
        except ValueError:
            log.warning(message)
            color = "red"
        else:
            wait_time = int(seconds)
            if minutes:
                wait_time += 60 * int(minutes)
            log.info("Waiting %d seconds to autoretry", wait_time)
            time.sleep(wait_time)
            return submit(answer=answer, level=level, day=day, year=year, session=session, reopen=reopen, quiet=quiet)
    if not quiet:
        cprint(message, color=color)
    return response


def main():
    parser = argparse.ArgumentParser(description="Advent of Code Data")
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    parser.add_argument(
        "day",
        nargs="?",
        type=int,
        choices=range(1,26),
        default=min(aoc_now.day, 25) if aoc_now.month == 12 else 1,
        help="1-25 (default: %(default)s)",
    )
    parser.add_argument(
        "year",
        nargs="?",
        type=int,
        choices=range(2015, aoc_now.year + int(aoc_now.month == 12)),
        default=most_recent_year(),
        help=">= 2015 (default: %(default)s)",
    )
    args = parser.parse_args()
    data = get_data(day=args.day, year=args.year)
    print(data)


class Aocd(object):
    _module = sys.modules[__name__]

    def __dir__(self):
        return __all__

    def __getattr__(self, name):
        if name == "data":
            day, year = get_day_and_year()
            return get_data(day=day, year=year)
        if name == "submit":
            day, year = get_day_and_year()
            return partial(submit, day=day, year=year)
        if name in dir(self):
            return globals()[name]
        raise AttributeError


sys.modules[__name__] = Aocd()


if __name__ == "__main__":  # pragma: no cover
    main()
