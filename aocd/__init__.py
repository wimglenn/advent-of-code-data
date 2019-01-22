import sys
from functools import partial

from .get import get_data, get_day_and_year
from .exceptions import AocdError
from .post import submit
from .version import __version__

from . import cli, exceptions, get, models, post, runner, utils, version


__all__ = [
    "data", "get_data", "get_answer", "main", "submit", "__version__",
    "AocdError", "PuzzleUnsolvedError", "AOC_TZ", "current_day",
    "most_recent_year", "get_cookie",
]


class Aocd(object):
    _module = sys.modules[__name__]

    def __dir__(self):
        return __all__

    def __getattr__(self, name):
        if name == "data":
            day, year = get_day_and_year()
            return get_data(day=day, year=year)
        if name == "submit":
            try:
                day, year = get_day_and_year()
            except AocdError:
                return submit
            else:
                return partial(submit, day=day, year=year)
        if name in dir(self):
            return globals()[name]
        raise AttributeError


sys.modules[__name__] = Aocd()
