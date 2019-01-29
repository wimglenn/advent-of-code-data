# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class User(object):
    def __init__(self, token):
        self.token = token

    @property
    def memo_dir(self):
        pass


class Puzzle(object):
    def __init__(self, year, day):
        self.year = year
        self.day = day

    @property
    def input_data(self):
        pass

    @property
    def correct_answer(self):
        pass

    @property
    def incorrect_answers(self):
        pass

    def submit_answer(self, value, level):
        pass

    def _save_correct_answer(self, value, level):
        pass

    def _save_incorrect_answer(self, value, level):
        pass
