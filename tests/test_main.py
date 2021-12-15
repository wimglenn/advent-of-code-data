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
    getter.assert_called_once_with(session=None, year=2015, day=8)


def test_main_valid_date_forgiving(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "2015", "8"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == "stuff\n"
    getter.assert_called_once_with(session=None, year=2015, day=8)


def test_main_user_guess(mocker, capsys):
    fake_users = {
        "bill": "b",
        "teddy": "t",
    }
    mocker.patch("aocd.cli._load_users", return_value=fake_users)
    mocker.patch("sys.argv", ["aocd", "2015", "8", "-u", "ted"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    getter.assert_called_once_with(session="t", year=2015, day=8)


def test_main_user_ambiguous(mocker, capsys):
    fake_users = {
        "billy": "b",
        "teddy": "t",
    }
    mocker.patch("aocd.cli._load_users", return_value=fake_users)
    mocker.patch("sys.argv", ["aocd", "2015", "8", "-u", "y"])
    with pytest.raises(SystemExit(2)):
        main()
    out, err = capsys.readouterr()
    assert "aocd: error: argument -u/--user: y ambiguous (could be billy, teddy)" in err


def test_main_user_exact(mocker, capsys):
    fake_users = {
        "bill": "b",
        "billy": "b2",
    }
    mocker.patch("aocd.cli._load_users", return_value=fake_users)
    mocker.patch("sys.argv", ["aocd", "2015", "8", "-u", "bill"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    getter.assert_called_once_with(session="b", year=2015, day=8)


def test_main_user_wat(mocker, capsys):
    fake_users = {
        "bill": "b",
        "teddy": "t",
    }
    mocker.patch("aocd.cli._load_users", return_value=fake_users)
    mocker.patch("sys.argv", ["aocd", "2015", "8", "-u", "z"])
    with pytest.raises(SystemExit(2)):
        main()
    out, err = capsys.readouterr()
    assert "aocd: error: argument -u/--user: invalid choice 'z' (choose from bill, teddy)" in err
