class User(object):
    def __init__(self, token):
        self.token = token


class Puzzle(object):
    def __init__(self, year, day):
        self.year = year
        self.day = day
