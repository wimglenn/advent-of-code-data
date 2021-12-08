from aocd.transforms import numbers


def test_get_numbers_csv():
    txt = "1,2,3\n"
    assert numbers(txt) == [1, 2, 3]


def test_get_numbers_whitespace():
    txt = "1 2 -3"
    assert numbers(txt) == [1, 2, -3]


def test_get_numbers_ragged():
    txt = "1,-2,3\n-4,5\n"
    assert numbers(txt) == [[1, -2, 3], [-4, 5]]


def test_get_numbers_ptp():
    txt = """
        68,788 -> 68,875
        858,142 -> 758,142
    """
    assert numbers(txt) == [
        [68, 788, 68, 875],
        [858, 142, 758, 142],
    ]
