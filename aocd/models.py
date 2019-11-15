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

import bs4
import pkg_resources
import requests
from termcolor import cprint

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
        self._user = user
        self.url = URL.format(year=self.year, day=self.day)
        self.input_data_url = self.url + "/input"
        self.submit_url = self.url + "/answer"
        prefix = self.user.memo_dir + "/{}_{:02d}".format(self.year, self.day)
        self.input_data_fname = prefix + "_input.txt"
        self.answer_a_fname = prefix + "a_answer.txt"
        self.answer_b_fname = prefix + "b_answer.txt"
        self.incorrect_answers_a_fname = prefix + "a_bad_answers.txt"
        self.incorrect_answers_b_fname = prefix + "b_bad_answers.txt"
        self.title_fname = AOCD_DIR + "/titles/{}_{:02d}.txt".format(
            self.year, self.day
        )
        self._cookies = {"session": self.user.token}
        self._headers = {"User-Agent": USER_AGENT}
        self._title = ""

    @property
    def user(self):
        return self._user

    @property
    def input_data(self):
        sanitized = "..." + self.user.token[-4:]
        try:
            # use previously received data, if any existing
            with io.open(self.input_data_fname, encoding="utf-8") as f:
                data = f.read()
        except (IOError, OSError) as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            sanitized_path = self.input_data_fname.replace(self.user.token, sanitized)
            log.debug("reusing existing data %s", sanitized_path)
            return data.rstrip("\r\n")
        log.info("getting data year=%s day=%s token=%s", self.year, self.day, sanitized)
        response = requests.get(
            url=self.input_data_url, cookies=self._cookies, headers=self._headers
        )
        if not response.ok:
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
    def title(self):
        if os.path.isfile(self.title_fname):
            with io.open(self.title_fname, encoding="utf-8") as f:
                self._title = f.read().strip()
        else:
            resp = requests.get(self.url, cookies=self._cookies, headers=self._headers)
            resp.raise_for_status()
            soup = bs4.BeautifulSoup(resp.text, "html.parser")
            self._save_title(soup=soup)
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
            raise AttributeError

    @answer_a.setter
    def answer_a(self, val):
        if isinstance(val, int):
            val = str(val)
        if getattr(self, "answer_a", None) == val:
            return
        self._submit(value=val, part="a")

    @property
    def answer_b(self):
        try:
            return self._get_answer(part="b")
        except PuzzleUnsolvedError:
            raise AttributeError

    @answer_b.setter
    def answer_b(self, val):
        if isinstance(val, int):
            val = str(val)
        if getattr(self, "answer_b", None) == val:
            return
        self._submit(value=val, part="b")

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
        bad_guesses = getattr(self, "incorrect_answers_" + part)
        if str(value) in bad_guesses:
            if not quiet:
                msg = "aocd will not submit that answer again. You've previously guessed {} and the server responded:"
                print(msg.format(value))
                cprint(bad_guesses[str(value)], "red")
            return
        url = self.submit_url
        sanitized = "..." + self.user.token[-4:]
        log.info("posting %r to %s (part %s) token=%s", value, url, part, sanitized)
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
                return self._submit(value=value, part=part, reopen=reopen, quiet=quiet)
        if not quiet:
            cprint(message, color=color)
        return response

    def _save_correct_answer(self, value, part):
        fname = getattr(self, "answer_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        txt = str(value).strip()
        msg = "saving the correct answer for %d/%02d part %s: %s"
        log.info(msg, self.year, self.day, part, txt)
        with open(fname, "w") as f:
            f.write(txt)

    def _save_incorrect_answer(self, value, part, extra=""):
        fname = getattr(self, "incorrect_answers_{}_fname".format(part))
        _ensure_intermediate_dirs(fname)
        msg = "appending an incorrect answer for %d/%02d part %s"
        log.info(msg, self.year, self.day, part)
        with open(fname, "a") as f:
            f.write(str(value).strip() + " " + extra.replace("\n", " ") + "\n")

    def _save_title(self, soup):
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
        have not already solved the puzzle, AocdError will be raised.
        """
        if part == "b" and self.day == 25:
            return None
        answer_fname = getattr(self, "answer_{}_fname".format(part))
        if os.path.isfile(answer_fname):
            with open(answer_fname) as f:
                return f.read().strip()
        # scrape puzzle page for any previously solved answers
        response = requests.get(self.url, cookies=self._cookies, headers=self._headers)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, "html.parser")
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
