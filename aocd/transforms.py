__all__ = ["lines", "numbers"]


def lines(data):
    return data.splitlines()


def numbers(data):
    return [int(n) for n in data.splitlines()]
