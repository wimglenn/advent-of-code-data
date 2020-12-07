import sys
import time
import tzlocal
from datetime import datetime
from itertools import cycle
from dateutil.tz import gettz

AOC_TZ = gettz("America/New_York")


def blocker(quiet=False, dt=0.1, datefmt="%-I:%M %p", until=None):
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
    while datetime.now(tz=AOC_TZ) < unlock:
        local_unlock = unlock.astimezone(tz=localzone)
        msg = "{} Unlock day {} at {:%s} ({:.0f}s remaining)" % datefmt
        remaining = (unlock - datetime.now(tz=AOC_TZ)).total_seconds()
        if not quiet:
            sys.stdout.write(msg.format(next(spinner), unlock.day, local_unlock, remaining))
            sys.stdout.flush()
        time.sleep(dt)
        if not quiet:
            sys.stdout.write("\r")
    if not quiet:
        # clears the "Unlock day" countdown line from the terminal
        sys.stdout.write("\r".ljust(80) + "\n")
        sys.stdout.flush()
