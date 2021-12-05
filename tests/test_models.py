from __future__ import unicode_literals

import logging
from datetime import timedelta

import os
import pytest
from requests.exceptions import HTTPError

from aocd.exceptions import AocdError
from aocd.exceptions import PuzzleUnsolvedError
from aocd.models import Puzzle
from aocd.models import User


def test_get_answer(aocd_data_dir):
    saved = aocd_data_dir / "testauth.testuser.000" / "2017_13b_answer.txt"
    saved.write_text("the answer")
    puzzle = Puzzle(day=13, year=2017)
    assert puzzle.answer_b == "the answer"


def test_get_answer_not_existing(aocd_data_dir, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/13")
    puzzle = Puzzle(day=13, year=2017)
    with pytest.raises(AttributeError("answer_b")):
        puzzle.answer_b


def test_get_answer_not_existing_ok_on_25dec(aocd_data_dir):
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2017_25a_answer.txt"
    answer_path.write_text("yeah")
    puzzle = Puzzle(day=25, year=2017)
    assert not puzzle.answer_b
    assert puzzle.answers == ("yeah", "")


def test_both_puzzle_answers_tuple(aocd_data_dir):
    answer_a_path = aocd_data_dir / "testauth.testuser.000" / "2016_06a_answer.txt"
    answer_b_path = aocd_data_dir / "testauth.testuser.000" / "2016_06b_answer.txt"
    answer_a_path.write_text("1234")
    answer_b_path.write_text("wxyz")
    puzzle = Puzzle(year=2016, day=6)
    assert puzzle.answers == ("1234", "wxyz")


def test_answered(aocd_data_dir):
    answer_a_path = aocd_data_dir / "testauth.testuser.000" / "2016_07a_answer.txt"
    answer_b_path = aocd_data_dir / "testauth.testuser.000" / "2016_07b_answer.txt"
    puzzle = Puzzle(year=2016, day=7)
    answer_a_path.write_text("foo")
    answer_b_path.write_text("")
    assert puzzle.answered_a is True
    assert puzzle.answered("a") is True
    assert puzzle.answered_b is False
    assert puzzle.answered("b") is False
    answer_a_path.write_text("")
    answer_b_path.write_text("bar")
    assert puzzle.answered_a is False
    assert puzzle.answered("a") is False
    assert puzzle.answered_b is True
    assert puzzle.answered("b") is True


def test_setattr_submits(mocker, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/7")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answer_a = 4321
    mock.assert_called_once_with(part="a", value="4321")


def test_setattr_doesnt_submit_if_already_done(mocker, aocd_data_dir):
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2017_07a_answer.txt"
    answer_path.write_text("someval")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answer_a = "someval"
    mock.assert_not_called()


def test_setattr_submit_both(aocd_data_dir, mocker, requests_mock):
    requests_mock.get("https://adventofcode.com/2017/day/7")
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2017_07a_answer.txt"
    answer_path.write_text("4321")
    puzzle = Puzzle(year=2017, day=7)
    mock = mocker.patch("aocd.models.Puzzle._submit")
    puzzle.answers = 4321, "zyxw"
    mock.assert_called_once_with(part="b", value="zyxw")


def test_setattr_doesnt_submit_both_if_done(mocker, aocd_data_dir):
    answer_a_path = aocd_data_dir / "testauth.testuser.000" / "2017_07a_answer.txt"
    answer_b_path = aocd_data_dir / "testauth.testuser.000" / "2017_07b_answer.txt"
    answer_a_path.write_text("ansA")
    answer_b_path.write_text("321")
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
    mock.assert_called_once_with(group="adventofcode.user")


def test_solve_one_plug(aocd_data_dir, mocker):
    input_path = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    input_path.write_text("someinput")
    ep = mocker.Mock()
    ep.name = "myplugin"
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([ep]))
    puzzle = Puzzle(year=2018, day=1)
    puzzle.solve()
    ep.load.return_value.assert_called_once_with(year=2018, day=1, data="someinput")


def test_solve_for(aocd_data_dir, mocker):
    input_path = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    input_path.write_text("blah")
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


def test_solve_for_unfound_user(aocd_data_dir, mocker):
    input_path = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    input_path.write_text("someinput")
    other_plug = mocker.Mock()
    other_plug.name = "otherplugin"
    mocker.patch("pkg_resources.iter_entry_points", return_value=iter([other_plug]))
    puzzle = Puzzle(year=2018, day=1)
    with pytest.raises(AocdError("No entry point found for 'myplugin'")):
        puzzle.solve_for("myplugin")
    other_plug.load.assert_not_called()
    other_plug.load.return_value.assert_not_called()


def test_get_title_failure(freezer, requests_mock, caplog):
    freezer.move_to("2018-12-01 12:00:00Z")
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text="<h2>Day 11: This SHOULD be day 1</h2>",
    )
    puzzle = Puzzle(year=2018, day=1)
    assert not puzzle.title
    msg = "weird heading, wtf? Day 11: This SHOULD be day 1"
    log_event = ("aocd.models", logging.ERROR, msg)
    assert log_event in caplog.record_tuples


def test_pprint(freezer, requests_mock, mocker):
    freezer.move_to("2018-12-01 12:00:00Z")
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text="<h2>Day 1: The Puzzle Title</h2>",
    )
    puzzle = Puzzle(year=2018, day=1)
    assert puzzle.title == "The Puzzle Title"
    printer = mocker.MagicMock()
    puzzle._repr_pretty_(printer, cycle=False)
    [((pretty,), kwargs)] = printer.text.call_args_list
    assert not kwargs
    assert pretty.startswith("<Puzzle(2018, 1) at 0x")
    assert pretty.endswith(" - The Puzzle Title>")


def test_pprint_cycle(freezer, requests_mock, mocker):
    freezer.move_to("2018-12-01 12:00:00Z")
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text="<h2>Day 1: The Puzzle Title</h2>",
    )
    puzzle = Puzzle(year=2018, day=1)
    assert puzzle.title == "The Puzzle Title"
    printer = mocker.MagicMock()
    puzzle._repr_pretty_(printer, cycle=True)
    [((pretty,), kwargs)] = printer.text.call_args_list
    assert not kwargs
    assert pretty.startswith("<aocd.models.Puzzle object at 0x")


fake_stats_response = """
<article><p>These are your personal leaderboard statistics.</p>
<pre>      <span class="leaderboard-daydesc-first">-------Part 1--------</span>
           <span class="leaderboard-daydesc-both">-------Part 2--------</span>
Day   <span class="leaderboard-daydesc-first">    Time  Rank  Score</span>
<span class="leaderboard-daydesc-both">    Time  Rank  Score</span>
 25       >24h  2708      0       >24h  1926      0
 24       >24h  2708      0          -     -      -
  4   00:03:30   158      0   00:04:17    25     76
  3   00:24:44   729      0   00:36:00   710      0
  2   01:11:16  4087      0   01:23:27  3494      0
  1   00:02:00   243      0   00:11:17   733      0
</pre>
</article>
"""


def test_get_stats(requests_mock):
    puzzle = Puzzle(year=2019, day=4)
    requests_mock.get(
        url="https://adventofcode.com/2019/leaderboard/self", text=fake_stats_response,
    )
    stats = puzzle.my_stats
    assert stats == {
        "a": {"time": timedelta(minutes=3, seconds=30), "rank": 158, "score": 0},
        "b": {"time": timedelta(minutes=4, seconds=17), "rank": 25, "score": 76},
    }


def test_get_stats_slow_user(requests_mock):
    puzzle = Puzzle(year=2019, day=25)
    requests_mock.get(
        url="https://adventofcode.com/2019/leaderboard/self", text=fake_stats_response,
    )
    stats = puzzle.my_stats
    assert stats == {
        "a": {"time": timedelta(hours=24), "rank": 2708, "score": 0},
        "b": {"time": timedelta(hours=24), "rank": 1926, "score": 0},
    }


def test_get_stats_fail(requests_mock):
    puzzle = Puzzle(year=2019, day=13)
    requests_mock.get(
        url="https://adventofcode.com/2019/leaderboard/self", text=fake_stats_response,
    )
    with pytest.raises(PuzzleUnsolvedError):
        puzzle.my_stats


def test_get_stats_partially_complete(requests_mock):
    puzzle = Puzzle(year=2019, day=24)
    requests_mock.get(
        url="https://adventofcode.com/2019/leaderboard/self", text=fake_stats_response,
    )
    stats = puzzle.my_stats
    assert stats == {
        "a": {"time": timedelta(hours=24), "rank": 2708, "score": 0},
    }


def test_puzzle_view(mocker):
    browser_open = mocker.patch("aocd.models.webbrowser.open")
    puzzle = Puzzle(year=2019, day=4)
    puzzle.view()
    browser_open.assert_called_once_with("https://adventofcode.com/2019/day/4")


def test_easter_eggs(requests_mock):
    requests_mock.get(
        url="https://adventofcode.com/2017/day/5",
        text=(
            '<article class="day-desc">'
            "<h2>--- Day 5: A Maze of Twisty Trampolines, All Alike ---</h2>"
            '<p>An urgent <span title="Later, on its turn, it sends you a '
            'sorcery.">interrupt</span> arrives from the CPU</p></article>'
        ),
    )
    puzzle = Puzzle(2017, 5)
    [egg] = puzzle.easter_eggs
    assert egg.text == "interrupt"
    assert egg.attrs["title"] == "Later, on its turn, it sends you a sorcery."


def test_get_stats_400(requests_mock):
    requests_mock.get(
        url="https://adventofcode.com/2015/leaderboard/self", status_code=400,
    )
    user = User("testtoken")
    with pytest.raises(HTTPError):
        user.get_stats()


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_unsolved(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", side_effect=PuzzleUnsolvedError)
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_guess_against_existing("one", "a")
    assert rv is None


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_empty(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_guess_against_existing("one", "a")
    assert rv is None


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_saved_correct(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="one")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_guess_against_existing("one", "a")
    assert rv == "Part a already solved with same answer: one"


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_saved_incorrect(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="two")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_guess_against_existing("one", "a")
    assert "Part a already solved with different answer: two" in rv


def test_owner_cache(aocd_config_dir):
    cache = aocd_config_dir / "token2id.json"
    cache.write_text('{"bleh": "a.u.n"}')
    user = User(token="bleh")
    user_id = user.id
    assert user_id == "a.u.n"
    assert str(user) == "<User a.u.n (token=...bleh)>"
