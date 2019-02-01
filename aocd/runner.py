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
import time
from argparse import ArgumentParser
from datetime import datetime
from pkg_resources import iter_entry_points

import pebble
from termcolor import colored

from .exceptions import AocdError
from .exceptions import PuzzleUnsolvedError
from .models import default_user
from .models import Puzzle
from .utils import AOC_TZ


# from https://adventofcode.com/about
# every problem has a solution that completes in at most 15 seconds on ten-year-old hardware


AOCD_DIR = os.path.expanduser(os.environ.get("AOCD_DIR", "~/.config/aocd"))
DEFAULT_TIMEOUT = 60


def main():
    users = {ep.name: ep for ep in iter_entry_points(group="adventofcode.user")}
    aoc_now = datetime.now(tz=AOC_TZ)
    all_years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    all_days = range(1, 26)
    path = AOCD_DIR + "/tokens.json"
    try:
        with open(path) as f:
            all_datasets = json.load(f)
    except IOError:
        all_datasets = {"default": default_user().token}
    parser = ArgumentParser(description="AoC runner")
    parser.add_argument("-u", "--users", choices=users)
    parser.add_argument("-y", "--years", type=int, nargs="+", choices=all_years)
    parser.add_argument("-d", "--days", type=int, nargs="+", choices=all_days)
    parser.add_argument("-D", "--data", nargs="+", choices=all_datasets)
    parser.add_argument("-t", "--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()
    if not all_datasets:
        print(
            "There are no datasets available.\n"
            "Either export your AOC_SESSION or list some datasets in {}".format(path),
            file=sys.stderr,
        )
        sys.exit(1)
    if not users:
        print(
            "There are no plugins available. Install some package(s) with a registered 'adventofcode.user' entry-point.\n"
            "See https://github.com/wimglenn/advent-of-code-sample for an example plugin package structure.",
            file=sys.stderr,
        )
        sys.exit(1)
    logging.basicConfig(level=getattr(logging, args.log_level))
    run_for(
        users=args.users or list(users),
        years=args.years or all_years,
        days=args.days or all_days,
        datasets={k: all_datasets[k] for k in (args.data or all_datasets)},
        timeout=args.timeout,
    )


def run_with_timeout(entry_point, timeout, progress, dt=0.1, **kwargs):
    # TODO : multi-process over the different tokens
    spinner = itertools.cycle(r"\|/-")
    pool = pebble.ProcessPool(max_workers=1)
    line = runtime = format_time(0)
    with pool:
        t0 = time.time()
        func = entry_point.load()
        future = pool.schedule(func, kwargs=kwargs, timeout=timeout)
        while not future.done():
            line = "\r" + runtime + "   " + progress + "   " + next(spinner)
            sys.stderr.write(line)
            sys.stderr.flush()
            time.sleep(dt)
            runtime = format_time(time.time() - t0)
        runtime = time.time() - t0
    sys.stderr.write("\r" + " " * len(line) + "\r")
    sys.stderr.flush()
    results = tuple(future.result()) + (runtime,)
    return results


def format_time(t, timeout=DEFAULT_TIMEOUT):
    if t < timeout / 4:
        color = "green"
    elif t < timeout / 2:
        color = "yellow"
    else:
        color = "red"
    runtime = colored("{: 7.2f}s".format(t), color)
    return runtime


def run_for(users, years, days, datasets, timeout=DEFAULT_TIMEOUT, autosubmit=True):
    aoc_now = datetime.now(tz=AOC_TZ)
    all_users_entry_points = iter_entry_points(group="adventofcode.user")
    entry_points = {ep.name: ep for ep in all_users_entry_points if ep.name in users}
    it = itertools.product(years, days, users, datasets)
    userpad = 3
    datasetpad = 8
    if entry_points:
        userpad = len(max(entry_points, key=len))
    if datasets:
        datasetpad = len(max(datasets, key=len))
    for year, day, user, dataset in it:
        if year == aoc_now.year and day > aoc_now.day:
            continue
        progress = "{year}/{day:<2d}   {user:>%d}/{dataset:<%d}" % (userpad, datasetpad)
        progress = progress.format(year=year, day=day, user=user, dataset=dataset)
        os.environ["AOC_SESSION"] = datasets[dataset]
        puzzle = Puzzle(year=year, day=day)
        data = puzzle.input_data
        entry_point = entry_points[user]
        t0 = time.time()
        crashed = False
        try:
            a, b, walltime = run_with_timeout(
                entry_point,
                timeout=timeout,
                year=year,
                day=day,
                data=data,
                progress=progress,
            )
        except Exception as err:
            crashed = True
            a = b = repr(err)
            walltime = time.time() - t0
        runtime = format_time(walltime, timeout)
        result_template = "   {icon} part {part}: {answer}"
        line = "   ".join([runtime, progress])
        for answer, part in zip((a, b), "ab"):
            if day == 25 and part == "b":
                # there's no part b on christmas day, skip
                continue
            expected = None
            try:
                expected = getattr(puzzle, "answer_" + part)
            except PuzzleUnsolvedError:
                post = part == "a" or (part == "b" and hasattr(puzzle, "answer_a"))
                if autosubmit and not crashed and post:
                    try:
                        puzzle._submit_answer(answer, part, reopen=False, quiet=True)
                        expected = getattr(puzzle, "answer_" + part)
                    except AocdError:
                        pass
            correct = str(expected) == answer
            icon = colored("✔", "green") if correct else colored("✖", "red")
            correction = ""
            if not correct:
                if expected is None:
                    icon = colored("?", "magenta")
                    correction = "(correct answer is unknown)"
                else:
                    correction = "(expected: {})".format(expected)
            answer = "{} {}".format(answer, correction)
            if part == "a":
                answer = answer.ljust(35)
            line += result_template.format(icon=icon, part=part, answer=answer)
        print(line)
