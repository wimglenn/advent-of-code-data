import pytest

from aocd.exceptions import AocdError
from aocd.models import Puzzle


def test_get_answer(aocd_dir):
    saved = aocd_dir / "thetesttoken/2017/13b_answer.txt"
    saved.ensure(file=True)
    saved.write("the answer")
    puzzle = Puzzle(day=13, year=2017)
    assert puzzle.answer_b == "the answer"


def test_get_answer_not_existing(aocd_dir, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/13")
    puzzle = Puzzle(day=13, year=2017)
    with pytest.raises(AttributeError):
        puzzle.answer_b


def test_both_puzzle_answers_tuple(aocd_dir):
    aocd_dir.join("thetesttoken/2016/6a_answer.txt").ensure(file=True).write("1234")
    aocd_dir.join("thetesttoken/2016/6b_answer.txt").ensure(file=True).write("wxyz")
    puzzle = Puzzle(year=2016, day=6)
    assert puzzle.answers == ("1234", "wxyz")


def test_setattr_submits(mocker, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/7")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answer_a = 4321
    mock.assert_called_once_with(part="a", value="4321")


def test_setattr_doesnt_submit_if_already_done(mocker, aocd_dir):
    aocd_dir.join("thetesttoken/2017/7a_answer.txt").ensure(file=True).write("someval")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answer_a = "someval"
    mock.assert_not_called()


def test_setattr_submit_both(aocd_dir, mocker, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/7")
    aocd_dir.join("thetesttoken/2017/7a_answer.txt").ensure(file=True).write("4321")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answers = 4321, "zyxw"
    mock.assert_called_once_with(part="b", value="zyxw")


def test_setattr_doesnt_submit_both_if_done(mocker, aocd_dir):
    aocd_dir.join("thetesttoken/2017/7a_answer.txt").ensure(file=True).write("ansA")
    aocd_dir.join("thetesttoken/2017/7b_answer.txt").ensure(file=True).write("321")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answers = "ansA", 321
    mock.assert_not_called()


def test_solve_no_plugs(mocker):
    mock = mocker.patch("pkg_resources.iter_entry_points", return_value=iter([]))
    puzzle = Puzzle(year=2018, day=1)
    expected = AocdError("Puzzle.solve is only available with unique entry point")
    with pytest.raises(expected):
        puzzle.solve()
    mock.assert_called_once_with("adventofcode.user")


def test_solve_one_plug(aocd_dir, mocker):
    aocd_dir.join("thetesttoken/2018/1.txt").ensure(file=True).write("someinput")
    ep = mocker.Mock()
    ep.name = "myplugin"
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    puzzle = Puzzle(year=2018, day=1)
    puzzle.solve()
    ep.load.return_value.assert_called_once_with(year=2018, day=1, data="someinput")


def test_solve_for(aocd_dir, mocker):
    aocd_dir.join("thetesttoken/2018/1.txt").ensure(file=True).write("blah")
    plug1 = mocker.Mock()
    plug1.name = "myplugin"
    plug2 = mocker.Mock()
    plug2.name = "otherplugin"
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([plug2, plug1]))
    puzzle = Puzzle(year=2018, day=1)
    puzzle.solve_for("myplugin")
    plug1.load.assert_called_once_with()
    plug1.load.return_value.assert_called_once_with(year=2018, day=1, data="blah")
    plug2.load.assert_not_called()
    plug2.load.return_value.assert_not_called()


def test_solve_for_unfound_user(aocd_dir, mocker):
    aocd_dir.join("thetesttoken/2018/1.txt").ensure(file=True).write("someinput")
    other_plug = mocker.Mock()
    other_plug.name = "otherplugin"
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([other_plug]))
    puzzle = Puzzle(year=2018, day=1)
    with pytest.raises(AocdError("No entry point found for 'myplugin'")):
        puzzle.solve_for("myplugin")
    other_plug.load.assert_not_called()
    other_plug.load.return_value.assert_not_called()
