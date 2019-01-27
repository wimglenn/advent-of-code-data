# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import datetime

from .get import get_data
from .get import most_recent_year
from .utils import AOC_TZ


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
