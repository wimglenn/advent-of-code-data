import argparse
import logging
import os
import platform
import shutil
import sys
import time
from collections import deque
from datetime import datetime
from functools import cache
from importlib.metadata import entry_points
from importlib.metadata import version
from itertools import cycle
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import bs4
import urllib3

from .exceptions import DeadTokenError


log = logging.getLogger(__name__)
AOC_TZ = ZoneInfo("America/New_York")
_v = version("advent-of-code-data")
USER_AGENT = f"github.com/wimglenn/advent-of-code-data v{_v} by hey@wimglenn.com"


class HttpClient:
    # every request to adventofcode.com goes through this wrapper
    # so that we can put in user agent header, rate-limit, etc.
    # aocd users should not need to use this class directly.

    def __init__(self):
        self.pool_manager = urllib3.PoolManager(headers={"User-Agent": USER_AGENT})
        self.req_count = {"GET": 0, "POST": 0}
        self._max_t = 3.0
        self._cooloff = 0.16
        self._history = deque([time.time() - self._max_t] * 4, maxlen=4)

    def _limiter(self):
        now = time.time()
        t0 = self._history[0]
        if now - t0 < self._max_t:
            # made 4 requests within 3 seconds - you're past the speed limit
            # of 1 req/second and will get a delay of 160ms initially, then
            # increasing exponentially on subsequent occasions. implemented
            # at the AoC author's request:
            #   https://github.com/wimglenn/advent-of-code-data/issues/59
            msg = "you're being rate-limited - slow down! (delay=%.02fs)"
            log.warning(msg, self._cooloff)
            time.sleep(self._cooloff)
            self._cooloff *= 2  # double it for repeat offenders
        self._history.append(now)

    def get(self, url, token=None, redirect=True):
        # getting user inputs, puzzle prose, etc
        if token is None:
            headers = self.pool_manager.headers
        else:
            headers = self.pool_manager.headers | {"Cookie": f"session={token}"}
        self._limiter()
        resp = self.pool_manager.request("GET", url, headers=headers, redirect=redirect)
        self.req_count["GET"] += 1
        return resp

    def post(self, url, token, fields):
        # submitting answers
        headers = self.pool_manager.headers | {"Cookie": f"session={token}"}
        self._limiter()
        resp = self.pool_manager.request_encode_body(
            method="POST",
            url=url,
            fields=fields,
            headers=headers,
            encode_multipart=False,
        )
        self.req_count["POST"] += 1
        return resp


http = HttpClient()


def _ensure_intermediate_dirs(path):
    path.expanduser().parent.mkdir(parents=True, exist_ok=True)


def blocker(quiet=False, dt=0.1, datefmt=None, until=None):
    """
    This function just blocks until the next puzzle unlocks.
    Pass `quiet=True` to disable the spinner etc.
    Pass `dt` (seconds) to update the status txt more/less frequently.
    Pass until=(year, day) to block until some other unlock date.
    """
    aoc_now = datetime.now(tz=AOC_TZ)
    month = 12
    if until is not None:
        year, day = until
    else:
        year = aoc_now.year
        day = aoc_now.day + 1
        if aoc_now.month < 12:
            day = 1
        elif aoc_now.day >= 25:
            day = 1
            year += 1
    unlock = datetime(year, month, day, tzinfo=AOC_TZ)
    if datetime.now(tz=AOC_TZ) > unlock:
        # it should already be unlocked - nothing to do
        return
    spinner = cycle(r"\|/-")
    localzone = datetime.now().astimezone().tzinfo
    local_unlock = unlock.astimezone(tz=localzone)
    if datefmt is None:
        # %-I does not work on Windows, strip leading zeros manually
        local_unlock = local_unlock.strftime("%I:%M %p").lstrip("0")
    else:
        local_unlock = local_unlock.strftime(datefmt)
    msg = "{} Unlock day %s at %s ({} remaining)" % (unlock.day, local_unlock)
    while datetime.now(tz=AOC_TZ) < unlock:
        remaining = unlock - datetime.now(tz=AOC_TZ)
        remaining = str(remaining).split(".")[0]  # trim microseconds
        if not quiet:
            sys.stdout.write(msg.format(next(spinner), remaining))
            sys.stdout.flush()
        time.sleep(dt)
        if not quiet:
            sys.stdout.write("\r")
    if not quiet:
        # clears the "Unlock day" countdown line from the terminal
        sys.stdout.write("\r".ljust(80) + "\n")
        sys.stdout.flush()


def get_owner(token):
    """
    Find owner of the token.
    Raises `DeadTokenError` if the token is expired/invalid.
    Returns a string like "authtype.username.userid"
    """
    url = "https://adventofcode.com/settings"
    response = http.get(url, token=token, redirect=False)
    if response.status != 200:
        # bad tokens will 302 redirect to main page
        log.info("session %s is dead - status_code=%s", token, response.status)
        raise DeadTokenError(f"the auth token ...{token[-4:]} is dead")
    soup = _get_soup(response.data)
    auth_source = "unknown"
    username = "unknown"
    userid = soup.code.text.split("-")[1]
    for span in soup.find_all("span"):
        if span.text.startswith("Link to "):
            auth_source = span.text[8:]
            auth_source = auth_source.replace("https://twitter.com/", "twitter/")
            auth_source = auth_source.replace("https://github.com/", "github/")
            auth_source = auth_source.replace("https://www.reddit.com/u/", "reddit/")
            auth_source, sep, username = auth_source.partition("/")
            if not sep:
                log.warning("problem in parsing %s", span.text)
                auth_source = username = "unknown"
            log.debug("found %r", span.text)
        elif span.img is not None:
            if "googleusercontent.com" in span.img.attrs.get("src", ""):
                log.debug("found google user content img, getting google username")
                auth_source = "google"
                username = span.text
                break
    result = ".".join([auth_source, username, userid])
    return result


def atomic_write_file(path, contents_str):
    """
    Atomically write a string to a file by writing it to a temporary file, and then
    renaming it to the final destination name. This solves a race condition where existence
    of a file doesn't necessarily mean the content is valid yet.
    """
    _ensure_intermediate_dirs(path)
    with NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as f:
        log.debug("writing to tempfile @ %s", f.name)
        f.write(contents_str)
    log.debug("moving %s -> %s", f.name, path)
    shutil.move(f.name, path)


def _cli_guess(choice, choices):
    # used by the argument parser so that you can specify user ids with a substring
    # (for example just specifying `-u git` instead of `--users github.wimglenn.119932`
    if choice in choices:
        return choice
    candidates = [c for c in choices if choice in c]
    if len(candidates) > 1:
        msg = f"{choice} ambiguous (could be {', '.join(candidates)})"
        raise argparse.ArgumentTypeError(msg)
    elif not candidates:
        msg = f"invalid choice {choice!r} (choose from {', '.join(choices)})"
        raise argparse.ArgumentTypeError(msg)
    [result] = candidates
    return result


_ansi_colors = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
if platform.system() == "Windows":
    os.system("color")  # hack - makes ANSI colors work in the windows cmd window


def colored(txt, color):
    if color is None:
        return txt
    code = _ansi_colors.index(color.casefold())
    reset = "\x1b[0m"
    return f"\x1b[{code + 30}m{txt}{reset}"


def get_plugins(group="adventofcode.user"):
    """
    Currently installed plugins for user solves.
    """
    try:
        # Python 3.10+
        return entry_points(group=group)
    except TypeError:
        # Python 3.9
        return entry_points().get(group, [])


@cache
def _get_soup(html):
    return bs4.BeautifulSoup(html, "html.parser")
