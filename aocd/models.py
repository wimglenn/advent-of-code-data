# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class User(object):
    def __init__(self, token):
        self.token = token


class Puzzle(object):
    def __init__(self, year, day):
        self.year = year
        self.day = day
