import json
import logging
import os
import re
import sys
import time
import webbrowser
from datetime import datetime
from datetime import timedelta
from functools import cache
from itertools import count
from pathlib import Path
from textwrap import dedent

from .example_parser import extract_examples
from .exceptions import AocdError
from .exceptions import DeadTokenError
from .exceptions import PuzzleLockedError
from .exceptions import PuzzleUnsolvedError
from .exceptions import UnknownUserError
from .utils import _ensure_intermediate_dirs
from .utils import AOC_TZ
from .utils import atomic_write_file
from .utils import colored
from .utils import get_owner
from .utils import get_plugins
from .utils import _get_soup
from .utils import http


log = logging.getLogger(__name__)


AOCD_DATA_DIR = Path(os.environ.get("AOCD_DIR", Path("~", ".config", "aocd")))
AOCD_DATA_DIR = AOCD_DATA_DIR.expanduser()
AOCD_CONFIG_DIR = Path(os.environ.get("AOCD_CONFIG_DIR", AOCD_DATA_DIR)).expanduser()
URL = "https://adventofcode.com/{year}/day/{day}"


class User:
    _token2id = None

    def __init__(self, token):
        self.token = token
        self._owner = "unknown.unknown.0"

    @classmethod
    def from_id(cls, id):
        users = _load_users()
        if id not in users:
            raise UnknownUserError(f"User with id '{id}' is not known")
        user = cls(users[id])
        user._owner = id
        return user

    @property
    def auth(self):
        """The header necessary to get user-specific puzzle input and prose"""
        return {"Cookie": f"session={self.token}"}

    @property
    def id(self):
        """User's token might change (they expire eventually) but the id found on AoC's
        settings page for a logged-in user is as close as we can get to a primary key.
        This id is used to key the cache, so that your caches aren't unnecessarily
        invalidated by being issued a new token"""
        fname = AOCD_CONFIG_DIR / "token2id.json"
        if User._token2id is None:
            try:
                User._token2id = json.loads(fname.read_text())
                log.debug("loaded user id memo from %s", fname)
            except FileNotFoundError:
                User._token2id = {}
        if self.token not in User._token2id:
            log.debug("token not found in memo, attempting to determine user id")
            owner = get_owner(self.token)
            log.debug("got owner=%s, adding to memo", owner)
            User._token2id[self.token] = owner
            _ensure_intermediate_dirs(fname)
            fname.write_text(json.dumps(User._token2id, sort_keys=True, indent=2))
        else:
            owner = User._token2id[self.token]
        if self._owner == "unknown.unknown.0":
            self._owner = owner
        return owner

    def __str__(self):
        return f"<{type(self).__name__} {self._owner} (token=...{self.token[-4:]})>"

    @property
    def memo_dir(self):
        """
        Directory where this user's puzzle inputs, answers etc. are stored on filesystem.
        """
        return AOCD_DATA_DIR / self.id

    def get_stats(self, years=None):
        """
        Parsed version of your personal stats (rank, solve time, score).
        See https://adventofcode.com/<year>/leaderboard/self when logged in.
        """
        aoc_now = datetime.now(tz=AOC_TZ)
        all_years = range(2015, aoc_now.year + int(aoc_now.month == 12))
        if isinstance(years, int) and years in all_years:
            years = (years,)
        if years is None:
            years = all_years
        days = {str(i) for i in range(1, 26)}
        results = {}
        headers = http.headers | self.auth
        ur_broke = "You haven't collected any stars"
        for year in years:
            url = f"https://adventofcode.com/{year}/leaderboard/self"
            response = http.request("GET", url, headers=headers, redirect=False)
            if 300 <= response.status < 400:
                # expired tokens 302 redirect to the overall leaderboard
                msg = f"the auth token ...{self.token[-4:]} is dead"
                raise DeadTokenError(msg)
            if response.status >= 400:
                raise AocdError(f"HTTP {response.status} at {url}")
            soup = _get_soup(response.data)
            if soup.article is None and ur_broke in soup.main.text:
                continue
            stats_txt = soup.article.pre.text
            lines = stats_txt.splitlines()
            lines = [x for x in lines if x.split()[0] in days]
            for line in reversed(lines):
                vals = line.split()
                day = int(vals[0])
                k = f"{year}/{day:02d}"
                results[k] = {}
                results[k]["a"] = {
                    "time": _parse_duration(vals[1]),
                    "rank": int(vals[2]),
                    "score": int(vals[3]),
                }
                if vals[4] != "-":
                    results[k]["b"] = {
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
        cookie = (AOCD_CONFIG_DIR / "token").read_text().split()[0]
    except FileNotFoundError:
        pass
    if cookie:
        return User(token=cookie)

    msg = dedent(
        f"""\
        ERROR: AoC session ID is needed to get your puzzle data!
        You can find it in your browser cookies after login.
            1) Save the cookie into a text file {AOCD_CONFIG_DIR / "token"}, or
            2) Export the cookie in environment variable AOC_SESSION

        See https://github.com/wimglenn/advent-of-code-wim/issues/1 for more info.
        """
    )
    print(colored(msg, color="red"), file=sys.stderr)
    raise AocdError("Missing session ID")


class Puzzle:
    def __init__(self, year, day, user=None):
        self.year = year
        self.day = day
        if user is None:
            user = default_user()
        self._user = user
        self.input_data_url = self.url + "/input"
        self.submit_url = self.url + "/answer"
        pre = self.user.memo_dir / f"{self.year}_{self.day:02d}"
        self.input_data_fname = pre.with_name(pre.name + "_input.txt")
        self.answer_a_fname = pre.with_name(pre.name + "a_answer.txt")
        self.answer_b_fname = pre.with_name(pre.name + "b_answer.txt")
        self.incorrect_answers_a_fname = pre.with_name(pre.name + "a_bad_answers.txt")
        self.incorrect_answers_b_fname = pre.with_name(pre.name + "b_bad_answers.txt")
        self.prose0_fname = AOCD_DATA_DIR / "prose" / (pre.name + "_prose.0.html")
        self.prose1_fname = pre.with_name(pre.name + "_prose.1.html")  # part a solved
        self.prose2_fname = pre.with_name(pre.name + "_prose.2.html")  # part b solved

    @property
    def user(self):
        return self._user

    @property
    def input_data(self):
        try:
            # use previously received data, if any existing
            data = self.input_data_fname.read_text()
        except FileNotFoundError:
            pass
        else:
            log.debug("reusing existing data %s", self.input_data_fname)
            return data.rstrip("\r\n")
        sanitized = "..." + self.user.token[-4:]
        log.info("getting data year=%s day=%s token=%s", self.year, self.day, sanitized)
        headers = http.headers | self.user.auth
        response = http.request("GET", url=self.input_data_url, headers=headers)
        if response.status >= 400:
            if response.status == 404:
                raise PuzzleLockedError(f"{self.year}/{self.day:02d} not available yet")
            log.error("got %s status code token=%s", response.status, sanitized)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {self.input_data_url}")
        data = response.data.decode()
        log.info("saving the puzzle input token=%s", sanitized)
        atomic_write_file(self.input_data_fname, data)
        return data.rstrip("\r\n")

    @property
    def examples(self):
        html = self._get_prose()
        try:
            examples = extract_examples(html)
        except Exception as err:
            msg = "unable to find example data for %d/%02d (%r)"
            log.warning(msg, self.year, self.day, err)
            examples = []
        return examples

    @property
    @cache
    def title(self):
        prose = self._get_prose()
        soup = _get_soup(prose)
        if soup.h2 is None:
            raise AocdError("heading not found")
        txt = soup.h2.text
        prefix = f"--- Day {self.day}: "
        suffix = " ---"
        if not txt.startswith(prefix) or not txt.endswith(suffix):
            raise AocdError(f"unexpected h2 text: {txt}")
        return txt.removeprefix(prefix).removesuffix(suffix)

    def _repr_pretty_(self, p, cycle):
        # this is a hook for IPython's pretty-printer
        if cycle:
            p.text(repr(self))
        else:
            txt = f"<Puzzle({self.year}, {self.day}) at {hex(id(self))} - {self.title}>"
            p.text(txt)

    def _coerce_val(self, val):
        orig_val = val
        orig_type = type(val)
        coerced = False
        floatish = isinstance(val, (float, complex))
        if floatish and val.imag == 0.0 and val.real.is_integer():
            coerced = True
            val = int(val.real)
        elif orig_type.__module__ == "numpy" and getattr(val, "ndim", None) == 0:
            # deal with numpy scalars
            if orig_type.__name__.startswith(("int", "uint", "long", "ulong")):
                coerced = True
                val = int(orig_val)
            elif orig_type.__name__.startswith(("float", "complex")):
                if val.imag == 0.0 and float(val.real).is_integer():
                    coerced = True
                    val = int(val.real)
        if isinstance(val, int):
            val = str(val)
        if coerced:
            log.warning(
                "coerced %s value %r for %d/%02d",
                orig_type.__name__,
                orig_val,
                self.year,
                self.day,
            )
        return val

    @property
    def answer_a(self):
        try:
            return self._get_answer(part="a")
        except PuzzleUnsolvedError:
            raise AttributeError("answer_a")

    @answer_a.setter
    def answer_a(self, val):
        val = self._coerce_val(val)
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
        val = self._coerce_val(val)
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
        if value in {"", b"", None, b"None", "None"}:
            raise AocdError(f"cowardly refusing to submit non-answer: {value!r}")
        if not isinstance(value, str):
            value = self._coerce_val(value)
        part = str(part).replace("1", "a").replace("2", "b").lower()
        if part not in {"a", "b"}:
            raise AocdError('part must be "a" or "b"')
        bad_guesses = getattr(self, "incorrect_answers_" + part)
        if value in bad_guesses:
            if not quiet:
                print(
                    "aocd will not submit that answer again. "
                    f"You've previously guessed {value} and the server responded:"
                )
                print(colored(bad_guesses[value], "red"))
            return
        if part == "b" and value == getattr(self, "answer_a", None):
            raise AocdError(
                f"cowardly refusing to submit {value} for part b, "
                "because that was the answer for part a"
            )
        url = self.submit_url
        check_guess = self._check_already_solved(value, part)
        if check_guess is not None:
            if quiet:
                log.info(check_guess)
            else:
                print(check_guess)
            return
        sanitized = "..." + self.user.token[-4:]
        log.info("posting %r to %s (part %s) token=%s", value, url, part, sanitized)
        level = {"a": "1", "b": "2"}[part]
        response = http.request_encode_body(
            "POST",
            url=url,
            headers=http.headers | self.user.auth,
            fields={"level": level, "answer": value},
            encode_multipart=False,
        )
        if response.status != 200:
            log.error("got %s status code", response.status)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {url}")
        soup = _get_soup(response.data)
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
                    rem = 49 - n_stars
                    log.info("Got %d stars, need %d more for part b", n_stars, rem)
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
            print(colored(message, color=color))
        return response

    def _check_already_solved(self, guess, part):
        try:
            answer = self._get_answer(part=part)
            if answer == "":
                return None
        except PuzzleUnsolvedError:
            return None
        msg = f"Part {part} already solved"
        if answer == guess:
            msg += f" with same answer: {answer}"
        else:
            msg += f" with different answer: {answer}"
            msg = colored(msg, "red")
        return msg

    def _save_correct_answer(self, value, part):
        fname = getattr(self, f"answer_{part}_fname")
        txt = value.strip()
        msg = "saving"
        if fname.is_file():
            prev = fname.read_text()
            if txt == prev:
                msg = "the correct answer for %d/%02d part %s was already saved"
                log.debug(msg, self.year, self.day, part)
                return
            msg = "overwriting"
        msg += " the correct answer for %d/%02d part %s: %s"
        log.info(msg, self.year, self.day, part, txt)
        _ensure_intermediate_dirs(fname)
        fname.write_text(txt)

    def _save_incorrect_answer(self, value, part, extra=""):
        fname = getattr(self, f"incorrect_answers_{part}_fname")
        msg = "appending an incorrect answer for %d/%02d part %s"
        log.info(msg, self.year, self.day, part)
        _ensure_intermediate_dirs(fname)
        if fname.is_file():
            txt = fname.read_text()
        else:
            txt = ""
        txt += value.strip() + " " + extra.replace("\n", " ") + "\n"
        fname.write_text(txt)

    def _get_answer(self, part):
        """
        Note: Answers are only revealed after a correct submission. If you've
        not already solved the puzzle, PuzzleUnsolvedError will be raised.
        """
        if part == "b" and self.day == 25:
            return ""
        answer_fname = getattr(self, f"answer_{part}_fname")
        if answer_fname.is_file():
            return answer_fname.read_text().strip()
        # check puzzle page for any previously solved answers.
        # if these were solved by typing into the website directly, rather than using
        # aocd submit, then our caches might not know about the answers yet.
        self._request_puzzle_page()
        if answer_fname.is_file():
            return answer_fname.read_text().strip()
        msg = f"Answer {self.year}-{self.day}{part} is not available"
        raise PuzzleUnsolvedError(msg)

    def _get_bad_guesses(self, part):
        fname = getattr(self, f"incorrect_answers_{part}_fname")
        result = {}
        if fname.is_file():
            for line in fname.read_text().splitlines():
                answer, _sep, extra = line.strip().partition(" ")
                result[answer] = extra
        return result

    def solve(self):
        try:
            [ep] = get_plugins()
        except ValueError:
            raise AocdError("Puzzle.solve is only available with unique entry point")
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    def solve_for(self, plugin):
        for ep in get_plugins():
            if ep.name == plugin:
                break
        else:
            raise AocdError(f"No entry point found for {plugin!r}")
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    @property
    def url(self):
        return URL.format(year=self.year, day=self.day)

    def view(self):
        webbrowser.open(self.url)

    @property
    def my_stats(self):
        """
        Your personal stats (rank, solve time, score) for this particular puzzle.
        Raises `PuzzleUnsolvedError` if you haven't actually solved it yet.
        """
        stats = self.user.get_stats(years=[self.year])
        key = f"{self.year}/{self.day:02d}"
        if key not in stats:
            raise PuzzleUnsolvedError
        result = stats[key]
        return result

    def _request_puzzle_page(self):
        headers = http.headers | self.user.auth
        response = http.request("GET", self.url, headers=headers)
        if response.status != 200:
            log.error("got %s status code", response.status)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {self.url}")
        self._last_resp = response
        text = response.data.decode()
        soup = _get_soup(text)
        hit = "Your puzzle answer was"
        if "Both parts of this puzzle are complete!" in text:  # solved
            if not self.prose2_fname.is_file():
                self.prose2_fname.write_text(text)
            hits = [p for p in soup.find_all("p") if p.text.startswith(hit)]
            if self.day == 25:
                [pa] = hits
            else:
                pa, pb = hits
                self._save_correct_answer(pb.code.text, "b")
            self._save_correct_answer(pa.code.text, "a")
        elif "The first half of this puzzle is complete!" in text:  # part b unlocked
            if not self.prose1_fname.is_file():
                self.prose1_fname.write_text(text)
            [pa] = [p for p in soup.find_all("p") if p.text.startswith(hit)]
            self._save_correct_answer(pa.code.text, "a")
        else:  # init, or dead token - doesn't really matter
            if not self.prose0_fname.is_file():
                _ensure_intermediate_dirs(self.prose0_fname)
                self.prose0_fname.write_text(text)

    def _get_prose(self):
        # prefer to return full prose (i.e. part b is solved or unlocked)
        # prefer to return prose with answers from same the user id as self.user.id
        for path in self.prose2_fname, self.prose1_fname:
            if path.is_file():
                log.debug("_get_prose using cached %s", path)
                return path.read_text()
            # see if other user has cached it
            other = next(AOCD_DATA_DIR.glob("*/" + path.name), None)
            if other is not None:
                log.debug("_get_prose using cached %s", other)
                return other.read_text()
        if self.prose0_fname.is_file():
            log.debug("_get_prose using cached %s", self.prose0_fname)
            return self.prose0_fname.read_text()
        self._request_puzzle_page()
        for path in self.prose2_fname, self.prose1_fname, self.prose0_fname:
            if path.is_file():
                log.debug("_get_prose using %s", path)
                return path.read_text()

    @property
    def easter_eggs(self):
        txt = self._get_prose()
        soup = _get_soup(txt)
        # Most puzzles have exactly one easter-egg, but 2018/12/17 had two..
        eggs = soup.find_all(["span", "em", "code"], class_=None, attrs={"title": bool})
        return eggs

    def unlock_time(self, local=True):
        """
        The time this puzzle unlocked. Might be in the future.
        If local is True (default), returns a datetime in your local zone.
        If local is False, returns a datetime in AoC's timezone (i.e. America/New_York)
        """
        result = datetime(self.year, 12, self.day, tzinfo=AOC_TZ)
        if local:
            localzone = datetime.now().astimezone().tzinfo
            result = result.astimezone(tz=localzone)
        return result

    @staticmethod
    def all(user=None):
        for year in count(2015):
            for day in range(1, 26):
                puzzle = Puzzle(year, day, user)
                if datetime.now(tz=AOC_TZ) < puzzle.unlock_time(local=False):
                    return
                yield puzzle


def _parse_duration(s):
    """Parse a string like 01:11:16 (hours, minutes, seconds) into a timedelta"""
    if s == ">24h":
        return timedelta(hours=24)
    h, m, s = [int(x) for x in s.split(":")]
    return timedelta(hours=h, minutes=m, seconds=s)


def _load_users():
    path = AOCD_CONFIG_DIR / "tokens.json"
    try:
        users = json.loads(path.read_text())
    except FileNotFoundError:
        users = {"default": default_user().token}
    return users
