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

from .utils import AOC_TZ
from .get import get_cookie
from .get import get_data
from .exceptions import PuzzleUnsolvedError
from .post import get_answer


# from https://adventofcode.com/about
# every problem has a solution that completes in at most 15 seconds on ten-year-old hardware


def main():
    users = {ep.name: ep for ep in iter_entry_points(group="adventofcode.user")}
    aoc_now = datetime.now(tz=AOC_TZ)
    all_years = range(2015, aoc_now.year + int(aoc_now.month == 12))
    all_days = range(1, 26)
    path = os.path.expanduser("~/.config/aocd/tokens.json")
    try:
        with open(path) as f:
            all_datasets = json.load(f)
    except IOError:
        all_datasets = {"default": get_cookie()}
    parser = ArgumentParser(description="AoC runner")
    parser.add_argument("-u", "--users", choices=users)
    parser.add_argument("-y", "--years", type=int, nargs="+", choices=all_years)
    parser.add_argument("-d", "--days", type=int, nargs="+", choices=all_days)
    parser.add_argument("-D", "--data", nargs="+", choices=all_datasets)
    parser.add_argument("-t", "--timeout", type=int, default=60)
    parser.add_argument(
        "--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()
    if not all_datasets:
        sys.exit(
            "There are no datasets available.\n"
            "Either export your AOC_SESSION or list some datasets in {}".format(path)
        )
    if not users:
        sys.exit(
            "There are no plugins available. Install some package(s) with a registered 'adventofcode.user' entry-point.\n"
            "See https://github.com/wimglenn/advent-of-code-sample for an example plugin package structure."
        )
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


def format_time(t, timeout=60):
    if t < timeout / 4:
        color = "green"
    elif t < timeout / 2:
        color = "yellow"
    else:
        color = "red"
    runtime = colored("{: 6.2f}s".format(t), color)
    return runtime


def run_for(users, years, days, datasets, timeout=60):
    aoc_now = datetime.now(tz=AOC_TZ)
    all_users_entry_points = iter_entry_points(group="adventofcode.user")
    entry_points = {ep.name: ep for ep in all_users_entry_points if ep.name in users}
    it = itertools.product(years, days, users, datasets)
    results = "{a_icon} part a: {part_a_answer} {b_icon} part b: {part_b_answer}"
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
        token = os.environ["AOC_SESSION"] = datasets[dataset]
        data = get_data(day=day, year=year, session=token)
        entry_point = entry_points[user]
        t0 = time.time()
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
            a = b = repr(err)
            walltime = time.time() - t0
        runtime = format_time(walltime, timeout)
        expected_a = expected_b = None
        try:
            expected_a = get_answer(day=day, year=year, session=token, level=1)
            expected_b = get_answer(day=day, year=year, session=token, level=2)
        except PuzzleUnsolvedError:
            pass
        a_correct = str(expected_a) == a
        b_correct = str(expected_b) == b
        a_icon = colored("✔", "green") if a_correct else colored("✖", "red")
        b_icon = colored("✔", "green") if b_correct else colored("✖", "red")
        a_correction = b_correction = ""
        if not a_correct:
            if expected_a is None:
                a_icon = colored("?", "magenta")
                a_correction = "(correct answer is unknown)"
            else:
                a_correction = "(expected: {})".format(expected_a)
        if not b_correct:
            if expected_b is None:
                b_icon = colored("?", "magenta")
                b_correction = "(correct answer is unknown)"
            else:
                b_correction = "(expected: {})".format(expected_b)
        part_a_answer = "{} {}".format(a, a_correction)
        part_b_answer = "{} {}".format(b, b_correction)
        line = "   ".join([runtime, progress, results])
        line = line.format(
            a_icon=a_icon,
            part_a_answer=part_a_answer.ljust(35),
            b_icon=b_icon,
            part_b_answer=part_b_answer,
        )
        if day == 25:
            # there's no part b on christmas day
            line = line.split(b_icon)[0].rstrip()
        print(line)
