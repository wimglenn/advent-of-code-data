"""
Transforms of aocd raw input text to something more useful for speed-solving.
Every function here needs to accept one positional argument and return the
'massaged' data.
"""

__all__ = ["lines", "numbers"]


def lines(data):
    return data.splitlines()


def numbers(data):
    return [int(n) for n in data.splitlines()]
