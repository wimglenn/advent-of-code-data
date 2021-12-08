"""
Transforms of aocd raw input text to something more useful for speed-solving.
Every function here needs to accept one positional argument and return the
'massaged' data.
"""

__all__ = ["lines", "numbers"]

import re


def lines(data):
    return data.splitlines()


def numbers(data):
    result = []
    for line in data.splitlines():
        matches = [int(n) for n in re.findall(r"-?\d+", line)]
        if matches:
            result.append(matches)
    if all(len(n) == 1 for n in result):
        # flatten the list if there is always 1 number per line
        result = [n for [n] in result]
    if len(result) == 1:
        # un-nest the list if there is only one line
        [result] = result
    return result
