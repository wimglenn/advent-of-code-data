import sys
from functools import partial

from . import cli
from . import cookies
from . import exceptions
from . import get
from . import models
from . import post
from . import runner
from . import utils
from . import _ipykernel
from .exceptions import AocdError
from .exceptions import PuzzleUnsolvedError
from .get import get_data
from .get import get_day_and_year
from .post import submit as _impartial_submit
from .utils import AOC_TZ


def __getattr__(name):
    if name == "data":
        day, year = get_day_and_year()
        return get_data(day=day, year=year)
    if name == "submit":
        try:
            day, year = get_day_and_year()
        except AocdError:
            return _impartial_submit
        else:
            return partial(_impartial_submit, day=day, year=year)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")



if sys.platform == "win32":
    import colorama

    colorama.init(autoreset=True)


# hackish - this tricks __getattr__ not to invoke importlib._bootstrap._handle_fromlist
del sys.modules[__name__].__path__
