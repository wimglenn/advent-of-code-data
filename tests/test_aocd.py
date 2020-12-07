import aocd
import pytest


def test_get_data_imported_from_class():
    from aocd import get_data

    assert aocd._module.get_data is get_data


def test_get_data_via_import(mocker):
    fake_stack = [("~/2017/q23.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mock = mocker.patch("aocd._module.get_data", return_value="test data")
    from aocd import data

    mock.assert_called_once_with(day=23, year=2017)
    assert data == "test data"


def test_import_submit_binds_day_and_year(mocker):
    fake_stack = [("~/2017/q23.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    from aocd import submit

    assert submit.func is aocd._module.submit  # partially applied
    submit.keywords == {"day": 23, "year": 2017}


def test_import_submit_doesnt_bind_day_and_year_when_introspection_failed(mocker):
    fake_stack = []
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    from aocd import submit

    assert submit is aocd._module.submit


def test_get_data_via_import_in_interactive_mode(monkeypatch, mocker, freezer):
    freezer.move_to("2017-12-10 12:00:00Z")
    monkeypatch.delattr("__main__.__file__")
    new_aocd = type(aocd)()
    mock = mocker.patch("aocd._module.get_data", return_value="repl data")
    data = new_aocd.data
    mock.assert_called_once_with(day=10, year=2017)
    assert data == "repl data"


def test_get_lines_via_import(mocker):
    fake_stack = [("~/2017/q23.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mock = mocker.patch("aocd._module.get_data", return_value="line 1\nline 2\nline 3")
    from aocd import lines

    mock.assert_called_once_with(day=23, year=2017)
    assert lines == ["line 1", "line 2", "line 3"]


def test_get_numbers_via_import(mocker):
    fake_stack = [("~/2017/q23.py",)]
    mocker.patch("aocd.get.traceback.extract_stack", return_value=fake_stack)
    mock = mocker.patch("aocd._module.get_data", return_value="1\n2\n3")
    from aocd import numbers

    mock.assert_called_once_with(day=23, year=2017)
    assert numbers == [1, 2, 3]


def test_attribute_errors_have_context():
    with pytest.raises(AttributeError("nope")):
        aocd.nope
