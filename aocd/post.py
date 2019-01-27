# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import re
import webbrowser
import time

import bs4
import requests
from termcolor import cprint

from .get import get_cookie
from .get import current_day
from .get import most_recent_year
from .exceptions import AocdError
from .exceptions import PuzzleUnsolvedError
from .utils import ensure_intermediate_dirs
from .utils import MEMO_FNAME
from .utils import URI
from .version import USER_AGENT


log = logging.getLogger(__name__)


def submit(answer, level=None, day=None, year=None, session=None, reopen=True, quiet=False):
    if level not in {1, 2, "1", "2", None}:
        raise AocdError("level must be 1 or 2")
    if session is None:
        session = get_cookie()
    if day is None:
        day = current_day()
    if year is None:
        year = most_recent_year()
    if level is None:
        # guess if user is submitting for part a or part b
        try:
            get_answer(day=day, year=year, session=session, level=1)
        except PuzzleUnsolvedError:
            log.debug("submitting for part a")
            level = 1
        else:
            log.debug("submitting for part b (part a is already completed)")
            level = 2
    bad_guesses = get_incorrect_answers(day=day, year=year, level=level, session=session)
    if str(answer) in bad_guesses:
        if not quiet:
            msg = "aocd will not submit that answer again. You've previously guessed {} and the server responded:"
            print(msg.format(answer))
            cprint(bad_guesses[str(answer)], "red")
        return
    uri = URI.format(year=year, day=day) + "/answer"
    log.info("posting to %s", uri)
    response = requests.post(
        uri,
        cookies={"session": session},
        headers={"User-Agent": USER_AGENT},
        data={"level": level, "answer": answer},
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
            webbrowser.open(response.url)  # So you can read part B on the website...
        save_correct_answer(answer=answer, day=day, year=year, level=level, session=session)
    elif "Did you already complete it" in message:
        color = "yellow"
    elif "That's not the right answer" in message:
        color = "red"
        you_guessed = soup.article.span.code.text
        log.warning("wrong answer %s", you_guessed)
        save_incorrect_answer(answer=answer, day=day, year=year, level=level, session=session, extra=soup.article.text)
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
            return submit(answer=answer, level=level, day=day, year=year, session=session, reopen=reopen, quiet=quiet)
    if not quiet:
        cprint(message, color=color)
    return response


def save_correct_answer(answer, day, year, level, session):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_answer.txt".format(part))
    ensure_intermediate_dirs(answer_fname)
    with open(answer_fname, "w") as f:
        log.info("saving the correct answer")
        f.write(str(answer).strip())


def save_incorrect_answer(answer, day, year, level, session, extra):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_bad_answers.txt".format(part))
    ensure_intermediate_dirs(answer_fname)
    with open(answer_fname, "a") as f:
        log.info("saving the wrong answer")
        f.write(str(answer).strip() + " " + extra.replace("\n", " ") + "\n")


def get_answer(day, year, session=None, level=1):
    """
    Get correct answer for day (1-25), year (>= 2015), and level (1 or 2)
    User's session cookie is needed (puzzle answers differ by user)
    Note: Answers are only revealed after a correct submission. If you
    have not already solved the puzzle, this AocdError will be raised.
    """
    if session is None:
        session = get_cookie()
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {1: "a", 2: "b"}[int(level)]
    answer_fname = memo_fname.replace(".txt", "{}_answer.txt".format(part))
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            return f.read().strip()
    # check question page for already solved answers
    uri = URI.format(year=year, day=day)
    response = requests.get(
        uri,
        cookies={"session": session},
        headers={"User-Agent": USER_AGENT},
    )
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    response.raise_for_status()
    paras = [p for p in soup.find_all('p') if p.text.startswith("Your puzzle answer was")]
    if paras:
        parta_correct_answer = paras[0].code.text
        save_correct_answer(answer=parta_correct_answer, day=day, year=year, level=1, session=session)
        if len(paras) > 1:
            _p1, p2 = paras
            partb_correct_answer = p2.code.text
            save_correct_answer(answer=partb_correct_answer, day=day, year=year, level=2, session=session)
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            return f.read().strip()
    msg = "Answer {}-{}{} is not available".format(year, day, part)
    raise PuzzleUnsolvedError(msg)


def get_incorrect_answers(day, year, level, session):
    memo_fname = MEMO_FNAME.format(session=session, year=year, day=day)
    part = {"1": "a", "2": "b"}[str(level)]
    answer_fname = memo_fname.replace(".txt", "{}_bad_answers.txt".format(part))
    result = {}
    if os.path.isfile(answer_fname):
        with open(answer_fname) as f:
            for line in f:
                answer, _sep, extra = line.strip().partition(" ")
                result[answer] = extra
    return result
