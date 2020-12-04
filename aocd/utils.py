import sys
import time
from datetime import datetime
from itertools import cycle
from dateutil.tz import gettz

AOC_TZ = gettz("America/New_York")


def blocker(quiet=False, dt=0.1):
    """
    This function just blocks until the next puzzle unlocks.
    Pass `quiet=True` to disable the spinner etc.
    Pass `dt` (seconds) to update the status txt more/less frequently.
    """
    aoc_now = datetime.now(tz=AOC_TZ)
    year = aoc_now.year
    month = 12
    day = aoc_now.day + 1
    if aoc_now.month < 12:
        day = 1
    elif aoc_now.day >= 25:
        day = 1
        year += 1
    unlock = datetime(year, month, day, tzinfo=AOC_TZ)
    spinner = cycle(r"\|/-")
    while datetime.now(tz=AOC_TZ) < unlock:
        msg = "{} Unlock day {} at midnight EST ({:.0f}s remaining)"
        remaining = (unlock - datetime.now(tz=AOC_TZ)).total_seconds()
        if not quiet:
            sys.stdout.write(msg.format(next(spinner), unlock.day, remaining))
            sys.stdout.flush()
        time.sleep(dt)
        if not quiet:
            sys.stdout.write("\r")
    if not quiet:
        sys.stdout.write("\r".ljust(80))
        sys.stdout.flush()
