# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import errno

import pytz


URL = "https://adventofcode.com/{year}/day/{day}"
AOC_TZ = pytz.timezone("America/New_York")
CONF_FNAME = os.path.expanduser("~/.config/aocd/token")
MEMO_FNAME = os.path.expanduser("~/.config/aocd/{session}/{year}/{day}.txt")


def ensure_intermediate_dirs(fname):
    parent = os.path.dirname(fname)
    try:
        os.makedirs(parent, exist_ok=True)
    except TypeError:
        # exist_ok not avail on Python 2
        try:
            os.makedirs(parent)
        except (IOError, OSError) as err:
            if err.errno != errno.EEXIST:
                raise
