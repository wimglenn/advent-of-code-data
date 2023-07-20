import contextlib
import itertools
import logging
import os
import sys
import tempfile
import time
from argparse import ArgumentParser
from datetime import datetime
from functools import partial
from pathlib import Path

import pebble.concurrent

from .exceptions import AocdError
from .models import _load_users
from .models import AOCD_CONFIG_DIR
from .models import Puzzle
from .utils import _cli_guess
from .utils import AOC_TZ
from .utils import colored
from .utils import get_plugins


# from https://adventofcode.com/about
# every problem has a solution that completes in at most 15 seconds on ten-year-old hardware


DEFAULT_TIMEOUT = 60
log = logging.getLogger(__name__)


def main():
    """
    Run user solver(s) against their inputs and render the results. Can use multiple
    tokens to validate your code against multiple input datas.
    """
    eps = get_plugins()
    plugins = {ep.name: ep for ep in eps}
    aoc_now = datetime.now(tz=AOC_TZ)
    years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    days = range(1, 26)
    users = _load_users()
    parser = ArgumentParser(description="AoC runner")
    parser.add_argument(
        "-p",
        "--plugins",
        nargs="+",
        choices=plugins,
        default=list(plugins),
        help=(
            "List of plugins (solvers) to evaluate. "
            "Runs against all available plugins by default."
        ),
    )
    parser.add_argument(
        "-y",
        "--years",
        metavar=f"({years[0]}-{years[-1]})",
        type=int,
        nargs="+",
        choices=years,
        default=years,
        help="AoC years to run. Runs all available by default.",
    )
    parser.add_argument(
        "-d",
        "--days",
        metavar=f"({days[0]}-{days[-1]})",
        type=int,
        nargs="+",
        choices=days,
        default=days,
        help="AoC days to run. Runs all 1-25 by default.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-e",
        "--example",
        action="store_true",
        help=(
            "Run against examples, instead of against real user data. "
            "This option is mutually exclusive with -u, because the sample "
            "data is the same for all users."
        ),
    )
    group.add_argument(
        "-u",
        "--users",
        nargs="+",
        choices=users,
        type=partial(_cli_guess, choices=users),
        default=users,
        help=(
            "Users to run each plugin with (e.g. your google token, your reddit token, "
            "your twitter token, your github token)."
        ),
    )
    parser.add_argument(
        "-t",
        "--timeout",
        metavar="T",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=(
            "Kill a solver if it exceeded this timeout, in seconds "
            "(default: %(default)s). Can use value '0' to disable timeout."
        ),
    )
    parser.add_argument(
        "-s",
        "--no-submit",
        action="store_false",
        dest="autosubmit",
        help=(
            "Disable autosubmit. "
            "By default, the runner will submit answers if necessary."
        ),
    )
    parser.add_argument(
        "-r",
        "--reopen",
        action="store_true",
        help="Open browser on NEW solves. Off by default.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help=(
            "Capture output from runner. "
            "Can be used to suppress unwanted terminal output from a plugin."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help=(
            "Increased logging (-v INFO, -vv DEBUG). "
            "Default level is logging.WARNING."
        ),
    )
    args = parser.parse_args()

    if not users:
        path = AOCD_CONFIG_DIR / "tokens.json"
        print(
            "There are no datasets available to use.\n"
            "Either export your AOC_SESSION or put some auth "
            f"tokens into {path}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not plugins:
        print(
            "There are no plugins available. Install some package(s) "
            "with a registered 'adventofcode.user' entry-point.\n"
            "See https://github.com/wimglenn/advent-of-code-sample "
            "for an example plugin package structure.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.verbose is None:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)
    rc = run_for(
        plugs=args.plugins,
        years=args.years,
        days=args.days,
        datasets={k: users[k] for k in args.users},
        example=args.example,
        timeout=args.timeout,
        autosubmit=args.autosubmit,
        reopen=args.reopen,
        capture=args.quiet,
    )
    sys.exit(rc)


def _timeout_wrapper(f, capture=False, timeout=DEFAULT_TIMEOUT, **kwargs):
    # aocd.runner executes the user's solve in a subprocess, so that it can be reliably
    # killed if it exceeds a time limit. you can't do that with threads.
    func = pebble.concurrent.process(daemon=False, timeout=timeout)(_process_wrapper)
    return func(f, capture, **kwargs)


def _process_wrapper(f, capture=False, **kwargs):
    # used to suppress any output from the subprocess, if aoc was invoked with --quiet
    with contextlib.ExitStack() as ctx:
        if capture:
            null = ctx.enter_context(open(os.devnull, "w"))
            ctx.enter_context(contextlib.redirect_stderr(null))
            ctx.enter_context(contextlib.redirect_stdout(null))
        return f(**kwargs)


def run_with_timeout(entry_point, timeout, progress, dt=0.1, capture=False, **kwargs):
    """
    Execute a user solve, and display a progress spinner as it's running. Kill it if
    the runtime exceeds `timeout` seconds.
    """
    spinner = itertools.cycle(r"\|/-")
    line = elapsed = format_time(0)
    t0 = time.time()
    func = entry_point.load()
    future = _timeout_wrapper(func, capture=capture, timeout=timeout, **kwargs)
    while not future.done():
        if progress is not None:
            line = "\r" + elapsed + "   " + progress + "   " + next(spinner)
            sys.stderr.write(line)
            sys.stderr.flush()
        time.sleep(dt)
        elapsed = format_time(time.time() - t0, timeout)
    walltime = time.time() - t0
    try:
        a, b = future.result()
    except Exception as err:
        a = b = ""
        error = repr(err)[:100]
    else:
        error = ""
        # longest correct answer seen so far has been 57 chars
        # that was the first example data from 2019/12/9 (i.e. the quine)
        a = str(a)[:60]
        b = str(b)[:60]
    if progress is not None:
        sys.stderr.write("\r" + " " * len(line) + "\r")
        sys.stderr.flush()
    return a, b, walltime, error


def format_time(t, timeout=DEFAULT_TIMEOUT):
    """
    Used for rendering the puzzle solve time in color:
    - green, if you're under a quarter of the timeout (15s default)
    - yellow, if you're over a quarter but under a half (30s by default)
    - red, if you're really slow (>30s by default)
    """
    if t < timeout / 4:
        color = "green"
    elif t < timeout / 2:
        color = "yellow"
    else:
        color = "red"
    runtime = colored(f"{t: 7.2f}s", color)
    return runtime


def run_one(
    year, day, data, entry_point, timeout=DEFAULT_TIMEOUT, progress=None, capture=False
):
    """
    Creates a temporary dir and change directory into it (restores cwd on exit).
    Lays down puzzle input in a file called "input.txt" in this directory - user code
    doesn't have to read this file if it doesn't want to, the puzzle input data will
    also be passed to the entry_point directly as a string.
    Execute user's puzzle solver (i.e. the `entry_point`) and capture the results.
    Returns a 4-tuple of:
        part a answer (computed by the user code)
        part b answer (computed by the user code)
        runtime of the solver (walltime)
        any error message (str) if the user code raised exception, empty string otherwise
    """
    prev = os.getcwd()
    scratch = tempfile.mkdtemp(prefix=f"{year}-{day:02d}-")
    os.chdir(scratch)
    input_path = Path("input.txt")
    assert not input_path.exists()
    try:
        input_path.write_text(data, encoding="utf-8")
        a, b, walltime, error = run_with_timeout(
            entry_point=entry_point,
            timeout=timeout,
            year=year,
            day=day,
            data=data,
            progress=progress,
            capture=capture,
        )
    finally:
        input_path.unlink(missing_ok=True)
        os.chdir(prev)
        try:
            os.rmdir(scratch)
        except Exception as err:
            log.warning("failed to remove scratch %s (%s: %s)", scratch, type(err), err)
    return a, b, walltime, error


def run_for(
    plugs,
    years,
    days,
    datasets,
    example=False,
    timeout=DEFAULT_TIMEOUT,
    autosubmit=True,
    reopen=False,
    capture=False,
):
    """
    Run with multiple users, multiple datasets, multiple years/days, and render the results.
    """
    if timeout == 0:
        timeout = float("inf")
    aoc_now = datetime.now(tz=AOC_TZ)
    eps = {ep.name: ep for ep in get_plugins() if ep.name in plugs}
    matrix = itertools.product(years, days, plugs)
    n_incorrect = 0
    # padding values for alignment
    wp = len(max(eps, key=len)) if eps else 3
    wd = len(max(datasets, key=len)) if datasets else 8
    for year, day, plugin in matrix:
        if year == aoc_now.year and day > aoc_now.day:
            continue
        entry_point = eps[plugin]
        puzzle = Puzzle(year, day)
        if example:
            autosubmit = False
            examples = Puzzle(year, day).examples
            datas = range(len(examples))
        else:
            datas = datasets
        for dataset in datas:
            if example:
                data = examples[dataset].input_data
            else:
                token = datasets[dataset]
                os.environ["AOC_SESSION"] = token
                puzzle = Puzzle(year, day)
                data = puzzle.input_data
            title = puzzle.title
            descr = f"example-{dataset + 1}" if example else dataset
            progress = f"{year}/{day:<2d} - {title:<40}   {plugin:>{wp}}/{descr:<{wd}}"
            a, b, walltime, error = run_one(
                year=year,
                day=day,
                data=data,
                entry_point=entry_point,
                timeout=timeout,
                progress=progress,
                capture=capture,
            )
            runtime = format_time(walltime, timeout)
            line = "   ".join([runtime, progress])
            if error:
                assert a == b == ""
                icon = colored("✖", "red")
                n_incorrect += 1
                line += f"   {icon} {error}"
            else:
                for answer, part in zip((a, b), "ab"):
                    if day == 25 and part == "b":
                        # there's no part b on christmas day, skip
                        continue
                    expected = None
                    try:
                        if example:
                            expected = getattr(examples[dataset], "answer_" + part)
                        else:
                            expected = getattr(puzzle, "answer_" + part)
                    except AttributeError:
                        post = part == "a" or (part == "b" and puzzle.answered_a)
                        if autosubmit and post:
                            try:
                                puzzle._submit(answer, part, reopen=reopen, quiet=True)
                            except AocdError as err:
                                log.warning("error submitting - %s", err)
                            try:
                                expected = getattr(puzzle, "answer_" + part)
                            except AttributeError:
                                pass
                    correct = expected is not None and str(expected) == answer
                    icon = colored("✔", "green") if correct else colored("✖", "red")
                    correction = ""
                    if not correct:
                        if expected is None:
                            icon = colored("?", "magenta")
                            correction = "(correct answer unknown)"
                        else:
                            correction = f"(expected: {expected})"
                            n_incorrect += 1
                    answer = f"{answer} {correction}"
                    if part == "a":
                        answer = answer.ljust(32)
                    if expected is None and example:
                        result = " " * 45
                    else:
                        result = f"   {icon} part {part}: {answer}"
                    line += result
            print(line)
    return n_incorrect
