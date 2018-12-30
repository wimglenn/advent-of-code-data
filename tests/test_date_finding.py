import pytest

import aocd
from aocd import AocdError


@pytest.mark.parametrize("date_str, expected_year", [
    ("2016-12-13 12:00:00Z", 2016),
    ("2016-12-30 12:00:00Z", 2016),
    ("2016-12-30 12:00:00Z", 2016),
    ("2016-11-30 12:00:00Z", 2015),
    ("2016-01-01 12:00:00Z", 2015),
])
def test_current_year(date_str, expected_year, freezer):
    freezer.move_to(date_str)
    year = aocd.most_recent_year()
    assert year == expected_year


def test_year_out_of_range(freezer):
    freezer.move_to("2015-11-11")
    with pytest.raises(AocdError("Time travel not supported yet")):
        aocd.most_recent_year()


@pytest.mark.parametrize("date_str, expected_day", [
    ("2016-12-01 00:00:01-05:00", 1),
    ("2016-12-02 23:30:00-05:00", 2),
    ("2016-12-02 23:30:00-06:00", 3),  # Chicago time - 1 hour ahead of AoC tz!
    ("2016-12-13 23:59:59-05:00", 13),
    ("2016-12-30 12:00:00-05:00", 25),
])
def test_current_day(date_str, expected_day, freezer):
    freezer.move_to(date_str)
    day = aocd.current_day()
    assert day == expected_day


def test_day_out_of_range(freezer):
    freezer.move_to("2015-11-11")
    with pytest.raises(AocdError("current_day is only available in December (EST)")):
        aocd.current_day()
