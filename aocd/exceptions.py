# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class AocdError(Exception):
    """base exception for this package"""


class PuzzleUnsolvedError(AocdError):
    """answer is unknown because user has not solved puzzle yet"""
