import errno
import os
import sys
import time
import tzlocal
from datetime import datetime
from itertools import cycle
from dateutil.tz import gettz

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
