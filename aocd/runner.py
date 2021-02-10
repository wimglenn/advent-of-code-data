# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import json
import logging
import os
import sys
import tempfile
import time
from argparse import ArgumentParser
from collections import OrderedDict
from datetime import datetime

import pebble.concurrent
import pkg_resources
from termcolor import colored

from .exceptions import AocdError
from .models import AOCD_DIR
from .models import default_user
from .models import Puzzle
from .utils import AOC_TZ


# from https://adventofcode.com/about
# every problem has a solution that completes in at most 15 seconds on ten-year-old hardware


DEFAULT_TIMEOUT = 60
log = logging.getLogger(__name__)


def main():
    entry_points = pkg_resources.iter_entry_points(group="adventofcode.user")
    plugins = OrderedDict([(ep.name, ep) for ep in entry_points])
    aoc_now = datetime.now(tz=AOC_TZ)
    years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    days = range(1, 26)
    path = os.path.join(AOCD_DIR, "tokens.json")
    try:
        with open(path) as f:
            users = json.load(f)
    except IOError:
        users = {"default": default_user().token}
    log_levels = "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    parser = ArgumentParser(description="AoC runner")
    parser.add_argument("-p", "--plugins", choices=plugins)
    parser.add_argument("-y", "--years", type=int, nargs="+", choices=years)
    parser.add_argument("-d", "--days", type=int, nargs="+", choices=days)
    parser.add_argument("-u", "--users", nargs="+", choices=users)
    parser.add_argument("-t", "--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("-s", "--no-submit", action="store_true", help="disable autosubmit")
    parser.add_argument("-r", "--reopen", action="store_true", help="open browser on NEW solves")
    parser.add_argument("--log-level", default="WARNING", choices=log_levels)
    args = parser.parse_args()
    if not users:
        print(
            "There are no datasets available to use.\n"
            "Either export your AOC_SESSION or put some auth "
            "tokens into {}".format(path),
            file=sys.stderr,
        )
        sys.exit(1)
    if not plugins:
        print(
            "There are no plugins available. Install some package(s) with a registered 'adventofcode.user' entry-point.\n"
            "See https://github.com/wimglenn/advent-of-code-sample for an example plugin package structure.",
            file=sys.stderr,
        )
        sys.exit(1)
    logging.basicConfig(level=getattr(logging, args.log_level))
    rc = run_for(
        plugins=args.plugins or list(plugins),
        years=args.years or years,
        days=args.days or days,
        datasets={k: users[k] for k in (args.users or users)},
        timeout=args.timeout,
        autosubmit=not args.no_submit,
        reopen=args.reopen,
    )
    sys.exit(rc)


@pebble.concurrent.process(daemon=False)
def _process_wrapper(f, *args, **kwargs):
    # allows to run f in a process which can be killed if it misbehaves
    return f(*args, **kwargs)


def run_with_timeout(entry_point, timeout, progress, dt=0.1, **kwargs):
    # TODO : multi-process over the different tokens
    spinner = itertools.cycle(r"\|/-")
    line = elapsed = format_time(0)
    t0 = time.time()
    func = entry_point.load()
    future = _process_wrapper(func, **kwargs)
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
        error = repr(err)[:50]
    else:
        error = ""
        # longest correct answer seen so far has been 32 chars
        a = str(a)[:50]
        b = str(b)[:50]
    if progress is not None:
        sys.stderr.write("\r" + " " * len(line) + "\r")
        sys.stderr.flush()
    return a, b, walltime, error


def format_time(t, timeout=DEFAULT_TIMEOUT):
    if t < timeout / 4:
        color = "green"
    elif t < timeout / 2:
        color = "yellow"
    else:
        color = "red"
    runtime = colored("{: 7.2f}s".format(t), color)
    return runtime


def run_one(year, day, input_data, entry_point, timeout=DEFAULT_TIMEOUT, progress=None):
    prev = os.getcwd()
    scratch = tempfile.mkdtemp(prefix="{}-{:02d}-".format(year, day))
    os.chdir(scratch)
    assert not os.path.exists("input.txt")
    try:
        with open("input.txt", "w") as f:
            f.write(input_data)
        a, b, walltime, error = run_with_timeout(
            entry_point=entry_point,
            timeout=timeout,
            year=year,
            day=day,
            data=input_data,
            progress=progress,
        )
    finally:
        os.unlink("input.txt")
        os.chdir(prev)
        os.rmdir(scratch)
    return a, b, walltime, error


def run_for(plugins, years, days, datasets, timeout=DEFAULT_TIMEOUT, autosubmit=True, reopen=False):
    aoc_now = datetime.now(tz=AOC_TZ)
    all_entry_points = pkg_resources.iter_entry_points(group="adventofcode.user")
    entry_points = {ep.name: ep for ep in all_entry_points if ep.name in plugins}
    it = itertools.product(years, days, plugins, datasets)
    userpad = 3
    datasetpad = 8
    n_incorrect = 0
    if entry_points:
        userpad = len(max(entry_points, key=len))
    if datasets:
        datasetpad = len(max(datasets, key=len))
    for year, day, plugin, dataset in it:
        if year == aoc_now.year and day > aoc_now.day:
            continue
        token = datasets[dataset]
        entry_point = entry_points[plugin]
        os.environ["AOC_SESSION"] = token
        puzzle = Puzzle(year=year, day=day)
        title = puzzle.title
        progress = "{}/{:<2d} - {:<40}   {:>%d}/{:<%d}"
        progress %= (userpad, datasetpad)
        progress = progress.format(year, day, title, plugin, dataset)
        a, b, walltime, error = run_one(
            year=year,
            day=day,
            input_data=puzzle.input_data,
            entry_point=entry_point,
            timeout=timeout,
            progress=progress,
        )
        runtime = format_time(walltime, timeout)
        line = "   ".join([runtime, progress])
        if error:
            assert a == b == ""
            icon = colored("✖", "red")
            n_incorrect += 1
            line += "   {icon} {error}".format(icon=icon, error=error)
        else:
            result_template = "   {icon} part {part}: {answer}"
            for answer, part in zip((a, b), "ab"):
                if day == 25 and part == "b":
                    # there's no part b on christmas day, skip
                    continue
                expected = None
                try:
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
                    n_incorrect += 1
                    if expected is None:
                        icon = colored("?", "magenta")
                        correction = "(correct answer unknown)"
                    else:
                        correction = "(expected: {})".format(expected)
                answer = "{} {}".format(answer, correction)
                if part == "a":
                    answer = answer.ljust(30)
                line += result_template.format(icon=icon, part=part, answer=answer)
        print(line)
    return n_incorrect
