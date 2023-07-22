import argparse
import datetime
import logging
from functools import partial
from importlib.metadata import version

from .get import get_data
from .get import most_recent_year
from .models import _load_users
from .models import Puzzle
from .utils import _cli_guess
from .utils import AOC_TZ
from .utils import get_plugins


def main():
    """Get your puzzle input data, caching it if necessary, and print it on stdout."""
    aoc_now = datetime.datetime.now(tz=AOC_TZ)
    days = range(1, 26)
    years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    users = _load_users()
    eps = get_plugins(group="adventofcode.examples")
    plugins = {ep.name: ep for ep in eps}
    parser = argparse.ArgumentParser(
        description=f"Advent of Code Data v{version('advent-of-code-data')}",
        usage=f"aocd [day 1-25] [year 2015-{years[-1]}]",
        formatter_class=argparse.RawTextHelpFormatter,
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
        help=f"2015-{years[-1]} (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s v{version('advent-of-code-data')}",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="enable debug logging",
    )
    if plugins:
        parser.add_argument(
            "-e",
            "--example-parser",
            nargs="?",
            choices=plugins,
            const="reference",
            help="get the example(s) data, if any",
        )
    if len(users) > 1:
        parser.add_argument(
            "-u",
            "--user",
            help=(
                "gets the data for a particular user.\n"
                "the known users are:\n"
                + "\n".join(" - " + u for u in users)
                + "\nuid may be specified by substring"
            ),
            metavar="<id>",
            choices=users,
            type=partial(_cli_guess, choices=users),
        )
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
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
    parser_name = getattr(args, "example_parser", None)
    if parser_name:
        puzzle = Puzzle(year=args.year, day=args.day)
        examples = puzzle._get_examples(parser_name)
        if not examples:
            print(f"no examples available for {args.year}/{args.day:02d}")
            return
        w = 80
        head = f"--- Day {puzzle.day}: {puzzle.title} ---"
        print(head.center(w, " "))
        print(puzzle.url.center(w, " "))
        for i, example in enumerate(examples, start=1):
            print(f" Example data {i}/{len(examples)} ".center(w, "-"))
            print(example.input_data)
            print("-" * w)
            print("answer_a:", example.answer_a or "-")
            print("answer_b:", example.answer_b or "-")
            if example.extra:
                print("extra:", example.extra)
            print("-" * w)
            print()
            print()
    else:
        data = get_data(session=session, day=args.day, year=args.year)
        print(data)
