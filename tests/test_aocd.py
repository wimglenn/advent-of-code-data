import functools

import pytest

import aocd


def test_aocd_data_with_attribute_access(mocker):
    fake_stack = [("~/2016/q22.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mock = mocker.patch("aocd.get_data", return_value="test data 2016/22")
    data = aocd.data
    mock.assert_called_once_with(day=22, year=2016)
    assert data == "test data 2016/22"


def test_aocd_data_with_from_import(mocker):
    fake_stack = [("~/2017/q23.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mock = mocker.patch("aocd.get_data", return_value="test data 2017/23")
    from aocd import data

    mock.assert_called_once_with(day=23, year=2017)
    assert data == "test data 2017/23"


def test_submit_autobinds_day_and_year(mocker):
    fake_stack = [("~/2017/q23.py", 1, "<test>", "from aocd import data")]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    submit = aocd.submit
    assert isinstance(submit, functools.partial)
    assert submit.func is aocd.post.submit
    # partially applied with day=23 and year=2017
    assert submit.keywords == {"day": 23, "year": 2017}


def test_submit_doesnt_bind_day_and_year_when_introspection_failed(mocker):
    fake_stack = []
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    assert not isinstance(aocd.submit, functools.partial)


def test_data_in_interactive_mode(monkeypatch, mocker, freezer):
    freezer.move_to("2017-12-10 12:00:00Z")
    monkeypatch.delattr("__main__.__file__")
    mock = mocker.patch("aocd.get_data", return_value="repl data")
    data = aocd.data
    mock.assert_called_once_with(day=10, year=2017)
    assert data == "repl data"


def test_attribute_errors_have_context():
    with pytest.raises(AttributeError("module 'aocd' has no attribute 'nope'")):
        aocd.nope
