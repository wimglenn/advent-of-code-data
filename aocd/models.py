# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import logging
import os
import re
import sys
import time
import webbrowser
from textwrap import dedent
from termcolor import cprint

import bs4
import requests

from .exceptions import AocdError
from .exceptions import PuzzleUnsolvedError
from .version import __version__


log = logging.getLogger(__name__)


AOCD_DIR = os.path.expanduser(os.environ.get("AOCD_DIR", "~/.config/aocd"))
URL = "https://adventofcode.com/{year}/day/{day}"
USER_AGENT = "advent-of-code-data v{}".format(__version__)


class User(object):
    def __init__(self, token):
        self.token = token

    @property
    def memo_dir(self):
        return AOCD_DIR + "/" + self.token


def default_user():
    # export your session id as AOC_SESSION env var
    cookie = os.getenv("AOC_SESSION")
    if cookie:
        return User(token=cookie)

    # or chuck it in a plaintext file at ~/.config/aocd/token
    try:
        with io.open(AOCD_DIR + "/token", encoding="utf-8") as f:
            cookie = f.read().strip()
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
        """
    )
    cprint(msg.format(AOCD_DIR + "/token"), color="red", file=sys.stderr)
    raise AocdError("Missing session ID")


class Puzzle(object):
    def __init__(self, year, day, user=None):
        self.year = year
        self.day = day
        if user is None:
            user = default_user()
        self.user = user
        self.url = URL.format(year=self.year, day=self.day)
        self.input_data_url = self.url + "/input"
        self.answer_submit_url = self.url + "/answer"
        prefix = self.user.memo_dir + "/{}/{}".format(self.year, self.day)
        self.input_data_fname = prefix + ".txt"
        self.answer_a_fname = prefix + "a_answer.txt"
        self.answer_b_fname = prefix + "b_answer.txt"
        self.bad_guesses_a_fname = prefix + "a_bad_answers.txt"
        self.bad_guesses_b_fname = prefix + "b_bad_answers.txt"
        self._cookies = {"session": self.user.token}
        self._headers = {"User-Agent": USER_AGENT}

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
            sanitized_fname = self.input_data_fname.replace(self.user.token, "<token>")
            log.info("reusing existing data %s", sanitized_fname)
            return data.rstrip("\r\n")
        log.info("getting data year=%s day=%s", self.year, self.day)
        response = requests.get(
            url=self.input_data_url, cookies=self._cookies, headers=self._headers
        )
        if not response.ok:
            log.error("got %s status code", response.status_code)
            log.error(response.text)
            raise AocdError("Unexpected response")
        data = response.text
        _ensure_intermediate_dirs(self.input_data_fname)
        with open(self.input_data_fname, "w") as f:
            log.info("saving the puzzle input")
            f.write(data)
        return data.rstrip("\r\n")

    @property
    def correct_answer_part_a(self):
        return self._get_answer(part="a")

    @property
    def correct_answer_part_b(self):
        return self._get_answer(part="b")

    @property
    def part_a_has_been_solved(self):
        try:
            self.correct_answer_part_a
        except PuzzleUnsolvedError:
            return False
        else:
            return True

    @property
    def part_b_has_been_solved(self):
        try:
            self.correct_answer_part_b
        except PuzzleUnsolvedError:
            return False
        else:
            return True

    @property
    def incorrect_answers_part_a(self):
        return self._bad_guesses(part="a")

    @property
    def incorrect_answers_part_b(self):
        return self._bad_guesses(part="b")

    def submit_answer(self, value, part, reopen=True, quiet=False):
        bad_guesses = getattr(self, "incorrect_answers_part_" + part)
        if str(value) in bad_guesses:
            if not quiet:
                msg = "aocd will not submit that answer again. You've previously guessed {} and the server responded:"
                print(msg.format(value))
                cprint(bad_guesses[str(value)], "red")
            return
        url = self.answer_submit_url
        log.info("posting %r to %s (part %s)", value, url, part)
        level = {"a": 1, "b": 2}[part]
        response = requests.post(
            url=url,
            cookies=self._cookies,
            headers=self._headers,
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
                webbrowser.open(response.url)
            self._save_correct_answer(value=value, part=part)
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
                return self.submit_answer(
                    value=value, part=part, reopen=reopen, quiet=quiet
                )
        if not quiet:
            cprint(message, color=color)
        return response

    def _save_correct_answer(self, value, part):
        fname = getattr(self, "answer_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        with open(fname, "w") as f:
            log.info("saving the correct answer")
            f.write(str(value).strip())

    def _save_incorrect_answer(self, value, part, extra=""):
        fname = getattr(self, "bad_guesses_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        with open(fname, "a") as f:
            log.info("saving the wrong answer")
            f.write(str(value).strip() + " " + extra.replace("\n", " ") + "\n")

    def _get_answer(self, part):
        """
        Note: Answers are only revealed after a correct submission. If you've
        have not already solved the puzzle, AocdError will be raised.
        """
        answer_fname = getattr(self, "answer_{}_fname".format(part))
        if os.path.isfile(answer_fname):
            with open(answer_fname) as f:
                return f.read().strip()
        # scrape puzzle page for any previously solved answers
        response = requests.get(self.url, cookies=self._cookies, headers=self._headers)
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        response.raise_for_status()
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

    def _bad_guesses(self, part):
        fname = getattr(self, "bad_guesses_{}_fname".format(part))
        result = {}
        if os.path.isfile(fname):
            with open(fname) as f:
                for line in f:
                    answer, _sep, extra = line.strip().partition(" ")
                    result[answer] = extra
        return result


def _ensure_intermediate_dirs(fname):
    parent = os.path.dirname(fname)
    try:
        os.makedirs(parent, exist_ok=True)
    except TypeError:
        # exist_ok not avail on Python 2
        try:
            os.makedirs(parent)
        except (IOError, OSError) as err:
            if err.errno != errno.EEXIST:
                raise
