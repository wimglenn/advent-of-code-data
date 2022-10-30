import typing as t

from aocd import cli, cookies, exceptions, get, models, post, runner, transforms, utils, version
from aocd.exceptions import AocdError, PuzzleUnsolvedError
from aocd.get import get_data
from aocd.post import submit
from aocd.utils import AOC_TZ
from aocd.version import __version__

__all__ = [
    "cli",
    "cookies",
    "exceptions",
    "get",
    "models",
    "post",
    "runner",
    "transforms",
    "utils",
    "version",
    "AocdError",
    "PuzzleUnsolvedError",
    "get_data",
    "submit",
    "AOC_TZ",
    "__version__",
    "data",
]

data: t.Text
lines: list[t.Text]
numbers: list[list[int]] | list[int] | int
