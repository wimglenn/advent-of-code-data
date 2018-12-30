import pytest

import aocd
from aocd import AocdError


introspect_date = aocd._module.introspect_date


def test_introspect_date_fail_no_filename_on_stack():
    with pytest.raises(AocdError("Failed introspection of filename")):
        introspect_date()


def test_introspect_date_from_stack(mocker):
    fake_stack = [("xmas_problem_2016_25b_dawg.py",)]
    mocker.patch("aocd._module.traceback.extract_stack", return_value=fake_stack)
    day, year = introspect_date()
    assert day == 25
    assert year == 2016


def test_year_is_ambiguous(mocker):
    fake_stack = [("~/2016/2017_q01.py",)]
    mocker.patch("aocd._module.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of year")):
        introspect_date()


def test_day_is_unknown(mocker):
    fake_stack = [("~/2016.py",)]
    mocker.patch("aocd._module.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        introspect_date()


def test_day_is_invalid(mocker):
    fake_stack = [("~/2016/q27.py",)]
    mocker.patch("aocd._module.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        introspect_date()
