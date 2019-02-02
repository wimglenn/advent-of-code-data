# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import json
import logging
import os
import pkg_resources
import sys
import time
from argparse import ArgumentParser
from collections import OrderedDict
from datetime import datetime

import pebble
from termcolor import colored

from .models import default_user
from .models import Puzzle
from .utils import AOC_TZ


# from https://adventofcode.com/about
# every problem has a solution that completes in at most 15 seconds on ten-year-old hardware


AOCD_DIR = os.path.expanduser(os.environ.get("AOCD_DIR", "~/.config/aocd"))
DEFAULT_TIMEOUT = 60


def main():
    entry_points = pkg_resources.iter_entry_points(group="adventofcode.user")
    plugins = OrderedDict([(ep.name, ep) for ep in entry_points])
    aoc_now = datetime.now(tz=AOC_TZ)
    years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    days = range(1, 26)
    path = AOCD_DIR + "/tokens.json"
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
    run_for(
        plugins=args.plugins or list(plugins),
        years=args.years or years,
        days=args.days or days,
        datasets={k: users[k] for k in (args.users or users)},
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
        results = tuple(future.result()) + (runtime,)
    sys.stderr.write("\r" + " " * len(line) + "\r")
    sys.stderr.flush()
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


def run_for(plugins, years, days, datasets, timeout=DEFAULT_TIMEOUT, autosubmit=True):
    aoc_now = datetime.now(tz=AOC_TZ)
    all_entry_points = pkg_resources.iter_entry_points(group="adventofcode.user")
    entry_points = {ep.name: ep for ep in all_entry_points if ep.name in plugins}
    it = itertools.product(years, days, plugins, datasets)
    userpad = 3
    datasetpad = 8
    if entry_points:
        userpad = len(max(entry_points, key=len))
    if datasets:
        datasetpad = len(max(datasets, key=len))
    for year, day, plugin, dataset in it:
        if year == aoc_now.year and day > aoc_now.day:
            continue
        os.environ["AOC_SESSION"] = datasets[dataset]
        puzzle = Puzzle(year=year, day=day)
        progress = "{0.year}/{0.day:<2d} - {0.title:<40}   {1:>%d}/{2:<%d}"
        progress %= (userpad, datasetpad)
        progress = progress.format(puzzle, plugin, dataset)
        t0 = time.time()
        crashed = False
        try:
            a, b, walltime = run_with_timeout(
                entry_point=entry_points[plugin],
                timeout=timeout,
                year=puzzle.year,
                day=puzzle.day,
                data=puzzle.input_data,
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
            except AttributeError:
                post = part == "a" or (part == "b" and hasattr(puzzle, "answer_a"))
                if autosubmit and not crashed and post:
                    try:
                        puzzle._submit(answer, part, reopen=False, quiet=True)
                        expected = getattr(puzzle, "answer_" + part)
                    except AttributeError:
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
                answer = answer.ljust(30)
            line += result_template.format(icon=icon, part=part, answer=answer)
        print(line)
