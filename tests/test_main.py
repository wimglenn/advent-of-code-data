import pytest

from aocd.cli import main


def test_main_invalid_date(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "1", "2014"])
    with pytest.raises(SystemExit(2)):
        main()
    out, err = capsys.readouterr()
    msg = "aocd: error: argument year: invalid choice: 2014 (choose from 2015, 2016, 2017, 2018"
    assert msg in err


def test_main_valid_date(mocker, capsys):
    mocker.patch("sys.argv", ["aocd", "8", "2015"])
    getter = mocker.patch("aocd.cli.get_data", return_value="stuff")
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == "stuff\n"
    getter.assert_called_once_with(year=2015, day=8)
