# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pytest
from termcolor import colored

from aocd.runner import main
from aocd.runner import run_for
from aocd.runner import format_time


def test_no_plugins_avail(capsys, mocker):
    mock = mocker.patch("pkg_resources.iter_entry_points", return_value=iter([]))
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
        "There are no datasets available to use.\n"
        "Either export your AOC_SESSION or put some auth tokens into {}\n".format(
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
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep1, ep2]))
    datasets_file = aocd_dir / "tokens.json"
    datasets_file.write('{"data1": "token1", "data2": "token2"}')
    mocker.patch("sys.argv", ["aoc", "--years=2015", "--days", "3", "7"])
    main()
    mock.assert_called_once_with(
        plugins=["user1", "user2"],
        years=[2015],
        days=[3, 7],
        datasets={"data1": "token1", "data2": "token2"},
        timeout=60,
    )


def fake_entry_point(year, day, data):
    assert year == 2015
    assert day == 1
    assert data == "testinput"
    return "answer1", "wrong"


def bugged_entry_point(year, day, data):
    raise Exception(123, 456)


def test_results(mocker, capsys):
    ep = mocker.Mock()
    ep.name = "testuser"
    worker = ep.load.return_value = fake_entry_point
    # worker = ep.load.return_value = lambda year, day, data: ("answer1", "wrong")  # TODO: why doesn't that work?
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    fake_puzzle = mocker.MagicMock()
    fake_puzzle.year = 2015
    fake_puzzle.day = 1
    fake_puzzle.input_data = "testinput"
    fake_puzzle.answer_a = "answer1"
    fake_puzzle.answer_b = "answer2"
    fake_puzzle.title = "The Puzzle Title"
    mocker.patch("aocd.runner.Puzzle", return_value=fake_puzzle)
    run_for(
        plugins=["testuser"],
        years=[2015],
        days=[1],
        datasets={"testdataset": "testtoken"},
    )
    ep.load.assert_called_once_with()
    out, err = capsys.readouterr()
    txt = "2015/1  - The Puzzle Title                           testuser/testdataset"
    assert txt in out
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


def test_nothing_to_do():
    run_for(plugins=[], years=[], days=[], datasets=[])


def test_day_out_of_range(mocker, capsys, freezer):
    freezer.move_to("2018-12-01 12:00:00Z")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    run_for(
        plugins=["testuser"],
        years=[2018],
        days=[27],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    assert out == err == ""


def test_run_crashed(aocd_dir, mocker, capsys):
    aocd_dir.join("titles/2018_25.txt").ensure(file=True).write("The Puzzle Title")
    aocd_dir.join("thetesttoken/2018_25_input.txt").ensure(file=True).write("someinput")
    aocd_dir.join("thetesttoken/2018_25a_answer.txt").ensure(file=True).write("answ")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = bugged_entry_point
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    run_for(
        plugins=["testuser"],
        years=[2018],
        days=[25],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    txt = "part a: Exception(123, 456) (expected: answ)"
    assert txt in out
    assert "part b" not in out  # because it's 25 dec, no part b puzzle


def test_run_and_autosubmit(aocd_dir, mocker, capsys, requests_mock):
    aocd_dir.join("titles/2015_01.txt").ensure(file=True).write("The Puzzle Title")
    aocd_dir.join("thetesttoken/2015_01_input.txt").ensure(file=True).write("testinput")
    aocd_dir.join("thetesttoken/2015_01a_answer.txt").ensure(file=True).write("answer1")
    requests_mock.get(url="https://adventofcode.com/2015/day/1")
    requests_mock.post(
        url="https://adventofcode.com/2015/day/1/answer",
        text="<article>That's not the right answer</article>",
    )
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    run_for(
        plugins=["testuser"],
        years=[2015],
        days=[1],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    assert "part a: answer1 " in out
    assert "part b: wrong (correct answer is unknown)" in out


def test_run_and_no_autosubmit(aocd_dir, mocker, capsys, requests_mock):
    aocd_dir.join("titles/2015_01.txt").ensure(file=True).write("The Puzzle Title")
    aocd_dir.join("thetesttoken/2015_01_input.txt").ensure(file=True).write("testinput")
    aocd_dir.join("thetesttoken/2015_01a_answer.txt").ensure(file=True).write("answer1")
    requests_mock.get(url="https://adventofcode.com/2015/day/1")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    run_for(
        plugins=["testuser"],
        years=[2015],
        days=[1],
        datasets={"default": "thetesttoken"},
        autosubmit=False,
    )
    out, err = capsys.readouterr()
    assert "part a: answer1 " in out
    assert "part b: wrong (correct answer is unknown)" in out
