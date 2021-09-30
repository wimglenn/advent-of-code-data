import bs4
import errno
import logging
import os
import requests
import sys
import time
import tzlocal
from datetime import datetime
from itertools import cycle
from dateutil.tz import gettz

from .exceptions import DeadTokenError


log = logging.getLogger(__name__)
AOC_TZ = gettz("America/New_York")


def _ensure_intermediate_dirs(fname):
    parent = os.path.dirname(os.path.expanduser(fname))
    try:
        os.makedirs(parent, exist_ok=True)
    except TypeError:
        # exist_ok not avail on Python 2
        try:
            os.makedirs(parent)
        except (IOError, OSError) as err:
            if err.errno != errno.EEXIST:
                raise


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
    localzone = tzlocal.get_localzone()
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
    """parse owner of the token. raises DeadTokenError if the token is expired/invalid.
    returns a string like authtype.username.userid"""
    url = "https://adventofcode.com/settings"
    response = requests.get(url, cookies={"session": token}, allow_redirects=False)
    if response.status_code != 200:
        # bad tokens will 302 redirect to main page
        log.info("session %s is dead - status_code=%s", token, response.status_code)
        raise DeadTokenError("the auth token ...{} is expired or not functioning".format(token[-4:]))
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    auth_source = "unknown"
    username = "unknown"
    userid = soup.code.text.split("-")[0]
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
