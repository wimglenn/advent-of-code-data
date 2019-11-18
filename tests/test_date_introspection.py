import pytest

from aocd.exceptions import AocdError
from aocd.get import get_day_and_year


def test_get_day_and_year_fail_no_filename_on_stack():
    with pytest.raises(AocdError("Failed introspection of filename")):
        get_day_and_year()


def test_get_day_and_year_from_stack(mocker):
    fake_stack = [("xmas_problem_2016_25b_dawg.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    day, year = get_day_and_year()
    assert day == 25
    assert year == 2016


def test_year_is_ambiguous(mocker):
    fake_stack = [("~/2016/2017_q01.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of year")):
        get_day_and_year()


def test_day_is_unknown(mocker):
    fake_stack = [("~/2016.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        get_day_and_year()


def test_day_is_invalid(mocker):
    fake_stack = [("~/2016/q27.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        get_day_and_year()
