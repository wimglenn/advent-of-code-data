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
from functools import cached_property
from importlib.metadata import entry_points
from itertools import count
from pathlib import Path
from textwrap import dedent

from . import examples
from .exceptions import AocdError
from .exceptions import DeadTokenError
from .exceptions import ExampleParserError
from .exceptions import PuzzleLockedError
from .exceptions import PuzzleUnsolvedError
from .exceptions import UnknownUserError
from .utils import _ensure_intermediate_dirs
from .utils import _get_soup
from .utils import AOC_TZ
from .utils import atomic_write_file
from .utils import colored
from .utils import get_owner
from .utils import get_plugins
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
    def id(self):
        """
        User's token might change (they expire eventually) but the id found on AoC's
        settings page for a logged-in user is as close as we can get to a primary key.
        This id is used to key the cache, so that your caches aren't unnecessarily
        invalidated when being issued a new token. That is, scraping a user id allows
        for aocd's caches to persist beyond multiple logout/logins.
        """
        path = AOCD_CONFIG_DIR / "token2id.json"
        if User._token2id is None:
            try:
                User._token2id = json.loads(path.read_text(encoding="utf-8"))
                log.debug("loaded user id memo from %s", path)
            except FileNotFoundError:
                User._token2id = {}
        if self.token not in User._token2id:
            log.debug("token not found in memo, attempting to determine user id")
            owner = get_owner(self.token)
            log.debug("got owner=%s, adding to memo", owner)
            User._token2id[self.token] = owner
            _ensure_intermediate_dirs(path)
            txt = json.dumps(User._token2id, sort_keys=True, indent=2)
            path.write_text(txt, encoding="utf-8")
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
        ur_broke = "You haven't collected any stars"
        for year in years:
            url = f"https://adventofcode.com/{year}/leaderboard/self"
            response = http.get(url, token=self.token, redirect=False)
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
    """
    Discover user's token from the environment or file, and exit with a diagnostic
    message if none can be found. This default user is used whenever a token or user id
    was otherwise unspecified.
    """
    # export your session id as AOC_SESSION env var
    cookie = os.getenv("AOC_SESSION")
    if cookie:
        return User(token=cookie)

    # or chuck it in a plaintext file at ~/.config/aocd/token
    try:
        cookie = (AOCD_CONFIG_DIR / "token").read_text(encoding="utf-8").split()[0]
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
        self.input_data_path = pre.with_name(pre.name + "_input.txt")
        self.answer_a_path = pre.with_name(pre.name + "a_answer.txt")
        self.answer_b_path = pre.with_name(pre.name + "b_answer.txt")
        self.submit_results_path = pre.with_name(pre.name + "_post.json")
        self.prose0_path = AOCD_DATA_DIR / "prose" / (pre.name + "_prose.0.html")
        self.prose1_path = pre.with_name(pre.name + "_prose.1.html")  # part a solved
        self.prose2_path = pre.with_name(pre.name + "_prose.2.html")  # part b solved

    @property
    def user(self):
        # this is a property to make it clear that it's read-only
        return self._user

    @property
    def input_data(self):
        """
        This puzzle's input data, specific to puzzle.user. It will usually be retrieved
        from caches, but if this is the first time it was accessed it will be requested
        from the server and then cached. Note that your puzzle inputs are associated
        with your user id, and will never change, they're safe to cache indefinitely.
        """
        try:
            # use previously received data, if any existing
            data = self.input_data_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            log.debug("input_data cache miss %s", self.input_data_path)
        else:
            log.debug("input_data cache hit %s", self.input_data_path)
            return data.rstrip("\r\n")
        sanitized = "..." + self.user.token[-4:]
        log.info("getting data year=%s day=%s token=%s", self.year, self.day, sanitized)
        response = http.get(self.input_data_url, token=self.user.token)
        if response.status >= 400:
            if response.status == 404:
                raise PuzzleLockedError(f"{self.year}/{self.day:02d} not available yet")
            log.error("got %s status code token=%s", response.status, sanitized)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {self.input_data_url}")
        data = response.data.decode()
        log.info("saving the puzzle input token=%s", sanitized)
        atomic_write_file(self.input_data_path, data)
        return data.rstrip("\r\n")

    @property
    def examples(self):
        """
        Sample data and answers associated with this puzzle, as a list of
        `aocd.examples.Example` instances. These are extracted from the puzzle prose
        html, and they're the same for every user id. This list might be empty (not
        every puzzle has usable examples), or it might have several examples, but it
        will usually have one element. The list, and the examples themselves, may be
        different depending on whether or not part b of the puzzle prose has been
        unlocked (i.e. part a has already been solved correctly).
        """
        return self._get_examples()

    def _get_examples(self, parser_name="reference"):
        # invoke a named example parser to extract examples from cached prose.
        # logs warning and returns an empty list if the parser plugin raises an
        # exception for any reason.
        try:
            page = examples.Page.from_raw(html=self._get_prose())
            parser = _load_example_parser(name=parser_name)
            if getattr(parser, "uses_real_datas", True):
                datas = examples._get_unique_real_inputs(self.year, self.day)
            else:
                datas = []
            result = parser(page, datas)
        except Exception as err:
            msg = "unable to find example data for %d/%02d (%r)"
            log.warning(msg, self.year, self.day, err)
            result = []
        return result

    @cached_property
    def title(self):
        """
        Title of the puzzle, used in the pretty repr (IPython etc) and also displayed
        by aocd.runner.
        """
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
        """Hook for IPython's pretty-printer."""
        if cycle:
            p.text(repr(self))
        else:
            txt = f"<Puzzle({self.year}, {self.day}) at {hex(id(self))} - {self.title}>"
            p.text(txt)

    def _coerce_val(self, val):
        # technically adventofcode.com will only accept strings as answers.
        # but it's convenient to be able to submit numbers, since many of the answers
        # are numeric strings. coerce the values to string safely.
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
        """
        The correct answer for the first part of the puzzle. This attribute hides
        itself if the first part has not yet been solved.
        """
        try:
            return self._get_answer(part="a")
        except PuzzleUnsolvedError:
            raise AttributeError("answer_a")

    @answer_a.setter
    def answer_a(self, val):
        """
        You can submit your answer to adventofcode.com by setting the answer attribute
        on a puzzle instance, e.g.

            puzzle.answer_a = "1234"

        The result of the submission will be printed to the terminal. It will only POST
        to the server if necessary.
        """
        val = self._coerce_val(val)
        if getattr(self, "answer_a", None) == val:
            return
        self._submit(value=val, part="a")

    @property
    def answered_a(self):
        """Has the first part of this puzzle been solved correctly yet?"""
        return bool(getattr(self, "answer_a", None))

    @property
    def answer_b(self):
        """
        The correct answer for the second part of the puzzle. This attribute hides
        itself if the second part has not yet been solved.
        """
        try:
            return self._get_answer(part="b")
        except PuzzleUnsolvedError:
            raise AttributeError("answer_b")

    @answer_b.setter
    def answer_b(self, val):
        """
        You can submit your answer to adventofcode.com by setting the answer attribute
        on a puzzle instance, e.g.

            puzzle.answer_b = "4321"

        The result of the submission will be printed to the terminal. It will only POST
        to the server if necessary.
        """
        val = self._coerce_val(val)
        if getattr(self, "answer_b", None) == val:
            return
        self._submit(value=val, part="b")

    @property
    def answered_b(self):
        """Has the second part of this puzzle been solved correctly yet?"""
        return bool(getattr(self, "answer_b", None))

    def answered(self, part):
        """Has the specified part of this puzzle been solved correctly yet?"""
        if part == "a":
            return bool(getattr(self, "answer_a", None))
        if part == "b":
            return bool(getattr(self, "answer_b", None))
        raise AocdError('part must be "a" or "b"')

    @property
    def answers(self):
        """
        Returns a tuple of the correct answers for this puzzle. Will raise an
        AttributeError if either part is yet to be solved by the associated user.
        """
        return self.answer_a, self.answer_b

    @answers.setter
    def answers(self, val):
        """
        Submit both answers at once. Pretty much impossible in practice, unless you've
        seen the puzzle before.
        """
        self.answer_a, self.answer_b = val

    @property
    def submit_results(self):
        """
        Record of all previous submissions to adventofcode.com for this user/puzzle.
        Submissions made by typing answers directly into the website will not be
        captured here, only submissions made by aocd itself are recorded.

        These previous submissions are cached to prevent submitting answers which are
        certain to be incorrect (for example, if the server told you that the answer
        "1234" was too high, then aocd will block you from submitting any higher value
        like "2468".

        The result of a previous submission made using puzzle answer setters can be
        seen with puzzle.submit_results[-1].
        """
        if self.submit_results_path.is_file():
            return json.loads(self.submit_results_path.read_text())
        return []

    def _submit(self, value, part, reopen=True, quiet=False):
        # actual submit logic. not meant to be invoked directly - users are expected
        # to use aocd.post.submit function, puzzle answer setters, or the aoc.runner
        # which autosubmits answers by default.
        if value in {"", b"", None, b"None", "None"}:
            raise AocdError(f"cowardly refusing to submit non-answer: {value!r}")
        if not isinstance(value, str):
            value = self._coerce_val(value)
        part = str(part).replace("1", "a").replace("2", "b").lower()
        if part not in {"a", "b"}:
            raise AocdError('part must be "a" or "b"')
        previous_submits = self.submit_results
        try:
            value_as_int = int(value)
        except ValueError:
            value_as_int = None
        skip_prefix = (
            "You gave an answer too recently",
            "You don't seem to be solving the right level",
        )
        for result in previous_submits:
            if result["part"] != part or result["message"].startswith(skip_prefix):
                continue
            if result["message"].startswith("That's the right answer"):
                if value != result["value"]:
                    if not quiet:
                        print(
                            "aocd will not submit that answer. "
                            f"At {result['when']} you've previously submitted "
                            f"{result['value']} and the server responded with:"
                        )
                        print(colored(result["message"], "green"))
                        print(
                            f"It is certain that {value!r} is incorrect, "
                            f"because {value!r} != {result['value']!r}."
                        )
                    return
            elif "your answer is too high" in result["message"]:
                if value_as_int is None or value_as_int > int(result["value"]):
                    if not quiet:
                        print(
                            "aocd will not submit that answer. "
                            f"At {result['when']} you've previously submitted "
                            f"{result['value']} and the server responded with:"
                        )
                        print(colored(result["message"], "red"))
                        print(
                            f"It is certain that {value!r} is incorrect, "
                            f"because {result['value']!r} was too high."
                        )
                    return
            elif "your answer is too low" in result["message"]:
                if value_as_int is None or value_as_int < int(result["value"]):
                    if not quiet:
                        print(
                            "aocd will not submit that answer. "
                            f"At {result['when']} you've previously submitted "
                            f"{result['value']} and the server responded with:"
                        )
                        print(colored(result["message"], "red"))
                        print(
                            f"It is certain that {value!r} is incorrect, "
                            f"because {result['value']!r} was too low."
                        )
                    return
            if result["value"] != value:
                continue
            if not quiet:
                print(
                    "aocd will not submit that answer again. "
                    f"At {result['when']} you've previously submitted "
                    f"{value} and the server responded with:"
                )
                if result["message"].startswith("That's the right answer"):
                    color = "green"
                else:
                    color = "red"
                print(colored(result["message"], color))
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
        fields = {"level": level, "answer": value}
        response = http.post(url, token=self.user.token, fields=fields)
        when = datetime.now(tz=AOC_TZ).isoformat(sep=" ")
        if response.status != 200:
            log.error("got %s status code", response.status)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {url}")
        soup = _get_soup(response.data)
        message = soup.article.text
        self._save_submit_result(value=value, part=part, message=message, when=when)
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
        else:
            log.warning("Unrecognised submit message %r", message)
        if not quiet:
            print(colored(message, color=color))
        return response

    def _check_already_solved(self, guess, part):
        # if you submit an answer on a puzzle which you've already solved, even if your
        # answer is correct, you get a sort of cryptic/confusing message back from the
        # server. this helper method prevents getting that.
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
        # cache the correct answers so that we know not to submit again
        path = getattr(self, f"answer_{part}_path")
        txt = value.strip()
        msg = "saving"
        if path.is_file():
            prev = path.read_text(encoding="utf-8")
            if txt == prev:
                msg = "the correct answer for %d/%02d part %s was already saved"
                log.debug(msg, self.year, self.day, part)
                return
            msg = "overwriting"
        msg += " the correct answer for %d/%02d part %s: %s"
        log.info(msg, self.year, self.day, part, txt)
        _ensure_intermediate_dirs(path)
        path.write_text(txt, encoding="utf-8")

    def _save_submit_result(self, value, part, message, when):
        # cache all submission results made by aocd. see the docstring of the
        # submit_results property for the reasons why.
        path = self.submit_results_path
        log.info("saving submit result for %d/%02d part %s", self.year, self.day, part)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            _ensure_intermediate_dirs(path)
            data = []
        data.append(
            {
                "part": part,
                "value": value,
                "when": when,
                "message": message,
            }
        )
        path.write_text(json.dumps(data, indent=2))

    def _get_answer(self, part):
        """
        Note: Answers are only revealed after a correct submission. If you've
        not already solved the puzzle, PuzzleUnsolvedError will be raised.
        """
        if part == "b" and self.day == 25:
            return ""
        answer_path = getattr(self, f"answer_{part}_path")
        if answer_path.is_file():
            return answer_path.read_text(encoding="utf-8").strip()
        # check puzzle page for any previously solved answers.
        # if these were solved by typing into the website directly, rather than using
        # aocd submit, then our caches might not know about the answers yet.
        self._request_puzzle_page()
        if answer_path.is_file():
            return answer_path.read_text(encoding="utf-8").strip()
        msg = f"Answer {self.year}-{self.day}{part} is not available"
        raise PuzzleUnsolvedError(msg)

    def solve(self):
        """
        If there is a unique entry-point in the "adventofcode.user" group, load it and
        invoke it using this puzzle's input data. It is expected to return a tuple of
        answers for part a and part b, respectively.

        Raise AocdError if there are no entry-points or multiple.
        """
        try:
            [ep] = get_plugins()
        except ValueError:
            raise AocdError("Puzzle.solve is only available with unique entry point")
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    def solve_for(self, plugin):
        """
        Load the entry-point from the "adventofcode.user" plugin group with the
        specified name, and invoke it using this puzzle's input data. The entry-point
        is expected to return a tuple of answers for part a and part b, respectively.

        Raise AocdError if the named plugin could not be found.
        """
        for ep in get_plugins():
            if ep.name == plugin:
                break
        else:
            raise AocdError(f"No entry point found for {plugin!r}")
        f = ep.load()
        return f(year=self.year, day=self.day, data=self.input_data)

    @property
    def url(self):
        """A link to the puzzle's description page on adventofcode.com."""
        return URL.format(year=self.year, day=self.day)

    def view(self):
        """Open this puzzle's description page in a new browser tab"""
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
        # hit the server to get the prose
        # cache the results so we don't have to get them again
        response = http.get(self.url, token=self.user.token)
        if response.status != 200:
            log.error("got %s status code", response.status)
            log.error(response.data.decode(errors="replace"))
            raise AocdError(f"HTTP {response.status} at {self.url}")
        self._last_resp = response
        text = response.data.decode()
        soup = _get_soup(text)
        hit = "Your puzzle answer was"
        if "Both parts of this puzzle are complete!" in text:  # solved
            if not self.prose2_path.is_file():
                _ensure_intermediate_dirs(self.prose2_path)
                self.prose2_path.write_text(text, encoding="utf-8")
            hits = [p for p in soup.find_all("p") if p.text.startswith(hit)]
            if self.day == 25:
                [pa] = hits
                self._save_correct_answer(pa.code.text, "a")
            else:
                pa, pb = hits
                self._save_correct_answer(pa.code.text, "a")
                self._save_correct_answer(pb.code.text, "b")
        elif "The first half of this puzzle is complete!" in text:  # part b unlocked
            if not self.prose1_path.is_file():
                _ensure_intermediate_dirs(self.prose1_path)
                self.prose1_path.write_text(text, encoding="utf-8")
            [pa] = [p for p in soup.find_all("p") if p.text.startswith(hit)]
            self._save_correct_answer(pa.code.text, "a")
        else:  # init, or dead token - doesn't really matter
            if not self.prose0_path.is_file():
                if "Advent of Code" in text:
                    _ensure_intermediate_dirs(self.prose0_path)
                    self.prose0_path.write_text(text, encoding="utf-8")

    def _get_prose(self):
        # prefer to return full prose (i.e. part b is solved or unlocked)
        # prefer to return prose with answers from same the user id as self.user.id
        for path in self.prose2_path, self.prose1_path:
            if path.is_file():
                log.debug("_get_prose cache hit %s", path)
                return path.read_text(encoding="utf-8")
            # see if other user has cached it
            other = next(AOCD_DATA_DIR.glob("*/" + path.name), None)
            if other is not None:
                log.debug("_get_prose cache hit %s", other)
                return other.read_text(encoding="utf-8")
        if self.prose0_path.is_file():
            log.debug("_get_prose cache hit %s", self.prose0_path)
            return self.prose0_path.read_text(encoding="utf-8")
        log.debug("_get_prose cache miss year=%d day=%d", self.year, self.day)
        self._request_puzzle_page()
        for path in self.prose2_path, self.prose1_path, self.prose0_path:
            if path.is_file():
                log.debug("_get_prose using %s", path)
                return path.read_text(encoding="utf-8")
        raise AocdError(f"Could not get prose for {self.year}/{self.day:02d}")

    @property
    def easter_eggs(self):
        """
        Return a list of Easter eggs in the puzzle's description page. When you've
        completed all 25 days, adventofcode.com will reveal the Easter eggs directly in
        the html, but this property works even if all days haven't been completed yet.
        Most puzzles have exactly one Easter egg, but 2018-12-17 had two, so this
        property always returns a list for consistency.
        """
        txt = self._get_prose()
        soup = _get_soup(txt)
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
        """
        Return an iterator over all known puzzles that are currently playable.
        """
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
    # loads the mapping between user ids and tokens. one user can have many tokens,
    # so we can't key the caches off of the token itself.
    path = AOCD_CONFIG_DIR / "tokens.json"
    try:
        users = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        users = {"default": default_user().token}
    return users


@cache
def _load_example_parser(group="adventofcode.examples", name="reference"):
    # lazy-loads a plugin used to parse sample data, and cache it
    try:
        # Python 3.10+ - group/name selectable entry points
        eps = entry_points().select(group=group, name=name)
    except AttributeError:
        # Python 3.9 - dict interface
        eps = [ep for ep in entry_points()[group] if ep.name == name]
    if not eps:
        msg = f"could not find the example parser plugin {group=}/{name=}"
        raise ExampleParserError(msg)
    if len(eps) > 1:
        log.warning("expected unique entrypoint but found %d entrypoints", len(eps))
    ep = next(iter(eps))
    parser = ep.load()
    log.debug("loaded example parser %r", parser)
    return parser
