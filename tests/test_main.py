import pytest

from aocd.cli import main


def test_main_invalid_date(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "1", "2014"])
    with pytest.raises(SystemExit(1)):
        main()
    out, err = capsys.readouterr()
    assert out.startswith("usage: aocd [day 1-25] [year 2015-")


def test_main_valid_date(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "8", "2015"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == "stuff\n"
    getter.assert_called_once_with(year=2015, day=8)


def test_main_valid_date_forgiving(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "2015", "8"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == "stuff\n"
    getter.assert_called_once_with(year=2015, day=8)
