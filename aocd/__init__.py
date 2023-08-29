import sys
from typing import TYPE_CHECKING, Union
from functools import partial

from . import cli
from . import cookies
from . import examples
from . import exceptions
from . import get
from . import models
from . import post
from . import runner
from . import utils
from .exceptions import AocdError
from .get import get_data
from .get import get_day_and_year
from .post import submit as _impartial_submit

__all__ = [
    "exceptions",
    "models",
    "AocdError",
    "get_data",
    "data",
    "submit",
]

data: str
lines: list[str]
numbers: Union[list[list[int]], list[int], int]

if TYPE_CHECKING:
    submit = _impartial_submit

def __getattr__(name): # type: ignore[no-untyped-def] # no idea how to provide meaningful types here
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


# pretend we're not a package, now that relative imports have been resolved.
# hackish - this prevents the import statement `from aocd import data` from going into
# importlib._bootstrap._handle_fromlist, which can cause __getattr__ to be called twice
del sys.modules[__name__].__path__
