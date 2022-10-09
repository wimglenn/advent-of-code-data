# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import json
import logging
import os
import re
import sys
import time
import webbrowser
from datetime import datetime
from datetime import timedelta
from textwrap import dedent

import bs4
import pkg_resources
import requests
from termcolor import colored
from termcolor import cprint

from .exceptions import AocdError
from .exceptions import UnknownUserError
from .exceptions import PuzzleUnsolvedError
from .exceptions import PuzzleLockedError
from .utils import AOC_TZ
from .utils import _ensure_intermediate_dirs
from .utils import get_owner
from .version import __version__


log = logging.getLogger(__name__)

AOCD_DATA_DIR = os.path.expanduser(os.environ.get("AOCD_DIR", os.path.join("~", ".config", "aocd")))
AOCD_CONFIG_DIR = os.path.expanduser(os.environ.get("AOCD_CONFIG_DIR", AOCD_DATA_DIR))
URL = "https://adventofcode.com/{year}/day/{day}"
USER_AGENT = {"User-Agent": "advent-of-code-data v{}".format(__version__)}


class User(object):

    _token2id = None

    def __init__(self, token):
        self.token = token
        self._owner = "unknown.unknown.0"

    @classmethod
    def from_id(cls, id):
        users = _load_users()
        if id not in users:
            raise UnknownUserError("User with id '{}' is not known".format(id))
        user = cls(users[id])
        user._owner = id
        return user

    @property
    def auth(self):
        return {"session": self.token}

    @property
    def id(self):
        fname = os.path.join(AOCD_CONFIG_DIR, "token2id.json")
        if User._token2id is None:
            try:
                with io.open(fname, encoding="utf-8") as f:
                    log.debug("loading user id memo from %s", fname)
                    User._token2id = json.load(f)
            except (IOError, OSError) as err:
                if err.errno != errno.ENOENT:
                    raise
                User._token2id = {}
        if self.token not in User._token2id:
            log.debug("token not found in memo, attempting to determine user id")
            owner = get_owner(self.token)
            log.debug("got owner=%s, adding to memo", owner)
            User._token2id[self.token] = owner
            _ensure_intermediate_dirs(fname)
            with open(fname, "w") as f:
                json.dump(User._token2id, f, sort_keys=True, indent=2)
        else:
            owner = User._token2id[self.token]
        if self._owner == "unknown.unknown.0":
            self._owner = owner
        return owner

    def __str__(self):
        return "<{} {} (token=...{})>".format(type(self).__name__, self._owner, self.token[-4:])

    @property
    def memo_dir(self):
        return os.path.join(AOCD_DATA_DIR, self.id)

    def get_stats(self, years=None):
        aoc_now = datetime.now(tz=AOC_TZ)
        all_years = range(2015, aoc_now.year + int(aoc_now.month == 12))
        if isinstance(years, int) and years in all_years:
            years = (years,)
        if years is None:
            years = all_years
        days = {str(i) for i in range(1, 26)}
        results = {}
        for year in years:
            url = "https://adventofcode.com/{}/leaderboard/self".format(year)
            response = requests.get(url, cookies=self.auth, headers=USER_AGENT)
            response.raise_for_status()
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            stats_txt = soup.article.pre.text
            lines = stats_txt.splitlines()
            lines = [x for x in lines if x.split()[0] in days]
            for line in reversed(lines):
                vals = line.split()
                day = int(vals[0])
                results[year, day] = {}
                results[year, day]["a"] = {
                    "time": _parse_duration(vals[1]),
                    "rank": int(vals[2]),
                    "score": int(vals[3]),
                }
                if vals[4] != "-":
                    results[year, day]["b"] = {
                        "time": _parse_duration(vals[4]),
                        "rank": int(vals[5]),
                        "score": int(vals[6]),
                    }
        return results


def default_user():
    # export your session id as AOC_SESSION env var
    cookie = os.getenv("AOC_SESSION")
    if cookie:
        return User(token=cookie)

    # or chuck it in a plaintext file at ~/.config/aocd/token
    try:
        with io.open(os.path.join(AOCD_CONFIG_DIR, "token"), encoding="utf-8") as f:
            cookie = f.read().split()[0]
    except (IOError, OSError) as err:
        if err.errno != errno.ENOENT:
            raise
    if cookie:
        return User(token=cookie)

    msg = dedent(
        """\
        ERROR: AoC session ID is needed to get your puzzle data!
        You can find it in your browser cookies after login.
            1) Save the cookie into a text file {}, or
            2) Export the cookie in environment variable AOC_SESSION

        See https://github.com/wimglenn/advent-of-code-wim/issues/1 for more info.
        """
    )
    cprint(msg.format(os.path.join(AOCD_CONFIG_DIR, "token")), color="red", file=sys.stderr)
    raise AocdError("Missing session ID")


class Puzzle(object):
    def __init__(self, year, day, user=None):
        self.year = year
        self.day = day
        if user is None:
            user = default_user()
        self._user = user
        self.input_data_url = self.url + "/input"
        self.submit_url = self.url + "/answer"
        fname = "{}_{:02d}".format(self.year, self.day)
        prefix = os.path.join(self.user.memo_dir, fname)
        self.input_data_fname = prefix + "_input.txt"
        self.example_input_data_fname = prefix + "_example_input.txt"
        self.answer_a_fname = prefix + "a_answer.txt"
        self.answer_b_fname = prefix + "b_answer.txt"
        self.incorrect_answers_a_fname = prefix + "a_bad_answers.txt"
        self.incorrect_answers_b_fname = prefix + "b_bad_answers.txt"
        self.title_fname = os.path.join(
            AOCD_DATA_DIR,
            "titles",
            "{}_{:02d}.txt".format(self.year, self.day)
        )
        self._title = ""

    @property
    def user(self):
        return self._user

    @property
    def input_data(self):
        try:
            # use previously received data, if any existing
            with io.open(self.input_data_fname, encoding="utf-8") as f:
                data = f.read()
        except (IOError, OSError) as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            log.debug("reusing existing data %s", self.input_data_fname)
            return data.rstrip("\r\n")
        sanitized = "..." + self.user.token[-4:]
        log.info("getting data year=%s day=%s token=%s", self.year, self.day, sanitized)
        response = requests.get(
            url=self.input_data_url, cookies=self.user.auth, headers=USER_AGENT
        )
        if not response.ok:
            if response.status_code == 404:
                raise PuzzleLockedError("{}/{:02d} not available yet".format(self.year, self.day))
            log.error("got %s status code token=%s", response.status_code, sanitized)
            log.error(response.text)
            raise AocdError("Unexpected response")
        data = response.text
        _ensure_intermediate_dirs(self.input_data_fname)
        with open(self.input_data_fname, "w") as f:
            log.info("saving the puzzle input token=%s", sanitized)
            f.write(data)
        return data.rstrip("\r\n")

    @property
    def example_data(self):
        try:
            with io.open(self.example_input_data_fname, encoding="utf-8") as f:
                data = f.read()
        except (IOError, OSError) as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            log.debug("reusing existing example data %s", self.example_input_data_fname)
            return data.rstrip("\r\n")
        soup = self._soup()
        try:
            data = soup.pre.text
        except Exception:
            log.info("unable to find example data year=%s day=%s", self.year, self.day)
            data = ""
        with open(self.example_input_data_fname, "w") as f:
            log.info("saving the example data")
            f.write(data)
        return data.rstrip("\r\n")

    @property
    def title(self):
        if os.path.isfile(self.title_fname):
            with io.open(self.title_fname, encoding="utf-8") as f:
                self._title = f.read().strip()
        else:
            self._save_title()
        return self._title

    def _repr_pretty_(self, p, cycle):
        # this is a hook for IPython's pretty-printer
        if cycle:
            p.text(repr(self))
        else:
            template = "<{0}({1.year}, {1.day}) at {2} - {1.title}>"
            p.text(template.format(type(self).__name__, self, hex(id(self))))

    @property
    def answer_a(self):
        try:
            return self._get_answer(part="a")
        except PuzzleUnsolvedError:
            raise AttributeError("answer_a")

    @answer_a.setter
    def answer_a(self, val):
        if isinstance(val, int):
            val = str(val)
        if getattr(self, "answer_a", None) == val:
            return
        self._submit(value=val, part="a")

    @property
    def answered_a(self):
        return bool(getattr(self, "answer_a", None))

    @property
    def answer_b(self):
        try:
            return self._get_answer(part="b")
        except PuzzleUnsolvedError:
            raise AttributeError("answer_b")

    @answer_b.setter
    def answer_b(self, val):
        if isinstance(val, int):
            val = str(val)
        if getattr(self, "answer_b", None) == val:
            return
        self._submit(value=val, part="b")

    @property
    def answered_b(self):
        return bool(getattr(self, "answer_b", None))

    def answered(self, part):
        if part == "a":
            return bool(getattr(self, "answer_a", None))
        if part == "b":
            return bool(getattr(self, "answer_b", None))
        raise AocdError('part must be "a" or "b"')

    @property
    def answers(self):
        return self.answer_a, self.answer_b

    @answers.setter
    def answers(self, val):
        self.answer_a, self.answer_b = val

    @property
    def incorrect_answers_a(self):
        return self._get_bad_guesses(part="a")

    @property
    def incorrect_answers_b(self):
        return self._get_bad_guesses(part="b")

    def _submit(self, value, part, reopen=True, quiet=False):
        if value in {u"", b"", None, b"None", u"None"}:
            raise AocdError("cowardly refusing to submit non-answer: {!r}".format(value))
        value = str(value)
        part = str(part).replace("1", "a").replace("2", "b").lower()
        if part not in {"a", "b"}:
            raise AocdError('part must be "a" or "b"')
        bad_guesses = getattr(self, "incorrect_answers_" + part)
        if value in bad_guesses:
            if not quiet:
                msg = "aocd will not submit that answer again. You've previously guessed {} and the server responded:"
                print(msg.format(value))
                cprint(bad_guesses[value], "red")
            return
        if part == "b" and value == getattr(self, "answer_a", None):
            raise AocdError("cowardly refusing to re-submit answer_a ({}) for part b".format(value))
        url = self.submit_url
        check_guess = self._check_guess_against_existing(value, part)
        if check_guess is not None:
            if quiet:
                log.info(check_guess)
            else:
                print(check_guess)
            return
        sanitized = "..." + self.user.token[-4:]
        log.info("posting %r to %s (part %s) token=%s", value, url, part, sanitized)
        level = {"a": 1, "b": 2}[part]
        response = requests.post(
            url=url,
            cookies=self.user.auth,
            headers=USER_AGENT,
            data={"level": level, "answer": value},
        )
        if not response.ok:
            log.error("got %s status code", response.status_code)
            log.error(response.text)
            raise AocdError("Non-200 response for POST: {}".format(response))
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        message = soup.article.text
        color = None
        if "That's the right answer" in message:
            color = "green"
            if reopen:
                # So you can read part B on the website...
                part_b_url = self.url + "#part2"
                log.info("reopening to %s", part_b_url)
                webbrowser.open(part_b_url)
            if not (self.day == 25 and part == "b"):
                self._save_correct_answer(value=value, part=part)
            if self.day == 25 and part == "a":
                log.debug("checking if got 49 stars already for year %s...", self.year)
                my_stats = self.user.get_stats(self.year)
                n_stars = sum(len(val) for val in my_stats.values())
                if n_stars == 49:
                    log.info("Got 49 stars already, getting 50th...")
                    self._submit(value="done", part="b", reopen=reopen, quiet=quiet)
                else:
                    log.info("Got %d stars, need %d more for part b", n_stars, 49 - n_stars)
        elif "Did you already complete it" in message:
            color = "yellow"
        elif "That's not the right answer" in message:
            color = "red"
            try:
                context = soup.article.span.code.text
            except AttributeError:
                context = soup.article.text
            log.warning("wrong answer: %s", context)
            self._save_incorrect_answer(value=value, part=part, extra=soup.article.text)
        elif "You gave an answer too recently" in message:
            wait_pattern = r"You have (?:(\d+)m )?(\d+)s left to wait"
            try:
                [(minutes, seconds)] = re.findall(wait_pattern, message)
            except ValueError:
                log.warning(message)
                color = "red"
            else:
                wait_time = int(seconds)
                if minutes:
                    wait_time += 60 * int(minutes)
                log.info("Waiting %d seconds to autoretry", wait_time)
                time.sleep(wait_time)
                return self._submit(value=value, part=part, reopen=reopen, quiet=quiet)
        if not quiet:
            cprint(message, color=color)
        return response

    def _check_guess_against_existing(self, guess, part):
        try:
            answer = self._get_answer(part=part)
            if answer == "":
                return None
        except PuzzleUnsolvedError:
            return None

        if answer == guess:
            template = "Part {part} already solved with same answer: {answer}"
        else:
            template = colored("Part {part} already solved with different answer: {answer}", "red")

        return template.format(part=part, answer=answer)

    def _save_correct_answer(self, value, part):
        fname = getattr(self, "answer_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        txt = value.strip()
        msg = "saving"
        if os.path.isfile(fname):
            with open(fname) as f:
                prev = f.read()
            if txt == prev:
                msg = "the correct answer for %d/%02d part %s was already saved"
                log.debug(msg, self.year, self.day, part)
                return
            msg = "overwriting"
        msg += " the correct answer for %d/%02d part %s: %s"
        log.info(msg, self.year, self.day, part, txt)
        with open(fname, "w") as f:
            f.write(txt)

    def _save_incorrect_answer(self, value, part, extra=""):
        fname = getattr(self, "incorrect_answers_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        msg = "appending an incorrect answer for %d/%02d part %s"
        log.info(msg, self.year, self.day, part)
        with open(fname, "a") as f:
            f.write(value.strip() + " " + extra.replace("\n", " ") + "\n")

    def _save_title(self, soup=None):
        if soup is None:
            soup = self._soup()
        if soup.h2 is None:
            log.warning("heading not found")
            return
        txt = soup.h2.text.strip("- ")
        prefix = "Day {}: ".format(self.day)
        if not txt.startswith(prefix):
            log.error("weird heading, wtf? %s", txt)
            return
        txt = self._title = txt[len(prefix) :]
        _ensure_intermediate_dirs(self.title_fname)
        with io.open(self.title_fname, "w", encoding="utf-8") as f:
            print(txt, file=f)

    def _get_answer(self, part):
        """
        Note: Answers are only revealed after a correct submission. If you've
        not already solved the puzzle, PuzzleUnsolvedError will be raised.
        """
        if part == "b" and self.day == 25:
            return ""
        answer_fname = getattr(self, "answer_{}_fname".format(part))
        if os.path.isfile(answer_fname):
            with open(answer_fname) as f:
                return f.read().strip()
        # scrape puzzle page for any previously solved answers
        soup = self._soup()
        if not self._title:
            # may as well save this while we're here
            self._save_title(soup=soup)
        hit = "Your puzzle answer was"
        paras = [p for p in soup.find_all("p") if p.text.startswith(hit)]
        if paras:
            parta_correct_answer = paras[0].code.text
            self._save_correct_answer(value=parta_correct_answer, part="a")
            if len(paras) > 1:
                _p1, p2 = paras
                partb_correct_answer = p2.code.text
                self._save_correct_answer(value=partb_correct_answer, part="b")
        if os.path.isfile(answer_fname):
            with open(answer_fname) as f:
                return f.read().strip()
        msg = "Answer {}-{}{} is not available".format(self.year, self.day, part)
        raise PuzzleUnsolvedError(msg)

    def _get_bad_guesses(self, part):
        fname = getattr(self, "incorrect_answers_{}_fname".format(part))
        result = {}
        if os.path.isfile(fname):
            with open(fname) as f:
                for line in f:
                    answer, _sep, extra = line.strip().partition(" ")
                    result[answer] = extra
        return result

    def solve(self):
        try:
            [ep] = pkg_resources.iter_entry_points(group="adventofcode.user")
        except ValueError:
            raise AocdError("Puzzle.solve is only available with unique entry point")
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    def solve_for(self, plugin):
        for ep in pkg_resources.iter_entry_points(group="adventofcode.user"):
            if ep.name == plugin:
                break
        else:
            raise AocdError("No entry point found for '{}'".format(plugin))
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    @property
    def url(self):
        return URL.format(year=self.year, day=self.day)

    def view(self):
        webbrowser.open(self.url)

    @property
    def my_stats(self):
        stats = self.user.get_stats(years=[self.year])
        if (self.year, self.day) not in stats:
            raise PuzzleUnsolvedError
        result = stats[self.year, self.day]
        return result

    def _soup(self):
        response = requests.get(self.url, cookies=self.user.auth, headers=USER_AGENT)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        return soup

    @property
    def easter_eggs(self):
        soup = self._soup()
        # Most puzzles have exactly one easter-egg, but 2018/12/17 had two..
        eggs = soup.find_all(["span", "em", "code"], class_=None, attrs={"title": bool})
        return eggs


def _parse_duration(s):
    """Parse a string like 01:11:16 (hours, minutes, seconds) into a timedelta"""
    if s == ">24h":
        return timedelta(hours=24)
    h, m, s = [int(x) for x in s.split(":")]
    return timedelta(hours=h, minutes=m, seconds=s)


def _load_users():
    path = os.path.join(AOCD_CONFIG_DIR, "tokens.json")
    try:
        with open(path) as f:
            users = json.load(f)
    except IOError:
        users = {"default": default_user().token}
    return users
