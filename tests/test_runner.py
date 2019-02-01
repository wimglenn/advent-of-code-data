# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pytest
from termcolor import colored

from aocd.exceptions import PuzzleUnsolvedError
from aocd.runner import main
from aocd.runner import run_for
from aocd.runner import format_time


def test_no_plugins_avail(capsys, mocker):
    mock = mocker.patch("aocd.runner.iter_entry_points", return_value=iter([]))
    mocker.patch("sys.argv", ["aoc"])
    msg = (
        "There are no plugins available. Install some package(s) with a registered 'adventofcode.user' entry-point.\n"
        "See https://github.com/wimglenn/advent-of-code-sample for an example plugin package structure.\n"
    )
    with pytest.raises(SystemExit(1)):
        main()
    out, err = capsys.readouterr()
    assert msg in err
    mock.assert_called_once_with(group="adventofcode.user")


def test_no_datasets_avail(capsys, mocker, aocd_dir):
    datasets_file = aocd_dir / "tokens.json"
    datasets_file.write("{}")
    mocker.patch("sys.argv", ["aoc"])
    msg = (
        "There are no datasets available.\n"
        "Either export your AOC_SESSION or list some datasets in {}\n".format(
            datasets_file
        )
    )
    with pytest.raises(SystemExit(1)):
        main()
    out, err = capsys.readouterr()
    assert msg in err


def test_main(capsys, mocker, aocd_dir):
    mock = mocker.patch("aocd.runner.run_for")
    ep1 = mocker.Mock()
    ep1.name = "user1"
    ep2 = mocker.Mock()
    ep2.name = "user2"
    mocker.patch("aocd.runner.iter_entry_points", return_value=iter([ep1, ep2]))
    datasets_file = aocd_dir / "tokens.json"
    datasets_file.write('{"data1": "token1", "data2": "token2"}')
    mocker.patch("sys.argv", ["aoc", "--years=2015", "--days", "3", "7"])
    main()
    mock.assert_called_once_with(
        users=["user1", "user2"],
        years=[2015],
        days=[3, 7],
        datasets={"data1": "token1", "data2": "token2"},
        timeout=60,
    )


def fake_entry_point(year, day, data):
    assert year == 2015
    assert day == 1
    assert data == "test input data"
    return "answer1", "wrong"


def test_results(mocker, capsys):
    ep = mocker.Mock()
    ep.name = "testuser"
    worker = ep.load.return_value = fake_entry_point
    # worker = ep.load.return_value = lambda year, day, data: ("answer1", "wrong")  # TODO: why doesn't that work?
    mocker.patch("aocd.runner.iter_entry_points", return_value=iter([ep]))
    fake_puzzle = mocker.MagicMock()
    fake_puzzle.input_data = "test input data"
    fake_puzzle.answer_a = "answer1"
    fake_puzzle.answer_b = "answer2"
    mocker.patch("aocd.runner.Puzzle", return_value=fake_puzzle)
    run_for(
        users=["testuser"],
        years=[2015],
        days=[1],
        datasets={"testdataset": "testtoken"},
    )
    ep.load.assert_called_once()
    out, err = capsys.readouterr()
    assert "2015/1    testuser/testdataset" in out
    assert "part a: answer1 " in out
    assert "part b: wrong (expected: answer2)" in out
    assert "✔" in out


@pytest.mark.parametrize(
    ("t", "timeout", "expected", "color"),
    [
        (2, 10, "   2.00s", "green"),
        (7, 10, "   7.00s", "red"),
        (111.5555, 400, " 111.56s", "yellow"),
    ],
)
def test_format_time(t, timeout, expected, color):
    actual = format_time(t, timeout)
    assert actual == colored(expected, color)
