# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import datetime
from functools import partial

from .get import get_data
from .get import most_recent_year
from .models import _load_users
from .utils import AOC_TZ
from .utils import _cli_guess
from .version import __version__


def main():
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    days = range(1, 26)
    years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    users = _load_users()
    parser = argparse.ArgumentParser(
        description="Advent of Code Data v{}".format(__version__),
        usage="aocd [day 1-25] [year 2015-{}]".format(years[-1]),
    )
    parser.add_argument(
        "day",
        nargs="?",
        type=int,
        default=min(aoc_now.day, 25) if aoc_now.month == 12 else 1,
        help="1-25 (default: %(default)s)",
    )
    parser.add_argument(
        "year",
        nargs="?",
        type=int,
        default=most_recent_year(),
        help="2015-{} (default: %(default)s)".format(years[-1]),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s v{}".format(__version__),
    )
    if len(users) > 1:
        parser.add_argument("-u", "--user", choices=users, type=partial(_cli_guess, choices=users))
    args = parser.parse_args()
    if args.day in years and args.year in days:
        # be forgiving
        args.day, args.year = args.year, args.day
    if args.day not in days or args.year not in years:
        parser.print_usage()
        parser.exit(1)
    try:
        session = users[args.user]
    except (KeyError, AttributeError):
        session = None
    data = get_data(session=session, day=args.day, year=args.year)
    print(data)
