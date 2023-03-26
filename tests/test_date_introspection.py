import os

import pytest

from aocd.exceptions import AocdError
from aocd.get import get_day_and_year


def test_get_day_and_year_fail_no_filename_on_stack():
    with pytest.raises(AocdError("Failed introspection of filename")):
        get_day_and_year()


def test_get_day_and_year_from_stack(mocker):
    stack = [("xmas_problem_2016_25b_dawg.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=stack)
    day, year = get_day_and_year()
    assert day == 25
    assert year == 2016


def test_year_is_ambiguous(mocker):
    fake_stack = [("~/2016/2017_q01.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of year")):
        get_day_and_year()


def test_day_is_unknown(mocker):
    fake_stack = [("~/2016.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        get_day_and_year()


def test_day_is_invalid(mocker):
    fake_stack = [("~/2016/q27.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    with pytest.raises(AocdError("Failed introspection of day")):
        get_day_and_year()


def test_ipynb_ok(mocker):
    fake_stack = [("ipykernel/123456789.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mocker.patch("aocd.get.get_ipynb_path", return_value="puzzle-2020-03.py")
    day, year = get_day_and_year()
    assert day == 3
    assert year == 2020


def test_ipynb_fail(mocker):
    fake_stack = [("ipykernel/123456789.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mocker.patch("aocd.get.get_ipynb_path", side_effect=ImportError)
    with pytest.raises(AocdError("Failed introspection of filename")):
        get_day_and_year()


def test_ipynb_fail_no_numbers_in_ipynb_filename(mocker):
    fake_stack = [("ipykernel/123456789.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mocker.patch("aocd.get.get_ipynb_path", "puzzle.py")
    with pytest.raises(AocdError("Failed introspection of filename")):
        get_day_and_year()


def test_no_numbers_in_py_filename_but_date_in_abspath(mocker):
    fname = os.sep.join(["adventofcode", "2022", "02", "main.py"])
    fake_stack = [(fname, 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    day, year = get_day_and_year()
    assert day == 2
    assert year == 2022
