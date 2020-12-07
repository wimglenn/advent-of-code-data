# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
from functools import partial

from . import cli
from . import cookies
from . import exceptions
from . import get
from . import models
from . import post
from . import runner
from . import transforms
from . import utils
from . import version
from .exceptions import AocdError
from .exceptions import PuzzleUnsolvedError
from .get import get_data
from .get import get_day_and_year
from .post import submit
from .utils import AOC_TZ
from .version import __version__


__all__ = [
    "cli",
    "cookies",
    "exceptions",
    "get",
    "models",
    "post",
    "runner",
    "utils",
    "version",
    "data",
    "get_data",
    "submit",
    "transforms",
    "__version__",
    "AocdError",
    "PuzzleUnsolvedError",
    "AOC_TZ",
]
__all__.extend(transforms.__all__)


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
        if name in transforms.__all__:
            transform = getattr(transforms, name)
            return transform(self.data)
        if name in dir(self):
            return globals()[name]
        raise AttributeError(name)


sys.modules[__name__] = Aocd()


if sys.platform == "win32":
    import colorama

    colorama.init(autoreset=True)
