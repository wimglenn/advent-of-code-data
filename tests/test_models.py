import logging
from datetime import datetime
from datetime import timedelta
from textwrap import dedent

import numpy as np
import pytest

from aocd.exceptions import AocdError
from aocd.exceptions import DeadTokenError
from aocd.exceptions import PuzzleUnsolvedError
from aocd.exceptions import UnknownUserError
from aocd.models import Puzzle
from aocd.models import User
from aocd.utils import AOC_TZ


def test_get_answer(aocd_data_dir):
    saved = aocd_data_dir / "testauth.testuser.000" / "2017_13b_answer.txt"
    saved.write_text("the answer")
    puzzle = Puzzle(day=13, year=2017)
    assert puzzle.answer_b == "the answer"


def test_get_answer_not_existing(aocd_data_dir, pook):
    pook.get("https://adventofcode.com/2017/day/13")
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
    with pytest.raises(AocdError('part must be "a" or "b"')):
        puzzle.answered(1)


def test_setattr_submits(mocker, pook):
    pook.get("https://adventofcode.com/2017/day/7")
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


def test_setattr_submit_both(aocd_data_dir, mocker, pook):
    pook.get("https://adventofcode.com/2017/day/7")
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
    mock = mocker.patch("aocd.models.get_plugins", return_value=[])
    puzzle = Puzzle(year=2018, day=1)
    expected = AocdError("Puzzle.solve is only available with unique entry point")
    with pytest.raises(expected):
        puzzle.solve()
    mock.assert_called_once_with()


def test_solve_one_plug(aocd_data_dir, mocker):
    input_path = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    input_path.write_text("someinput")
    ep = mocker.Mock()
    ep.name = "myplugin"
    mocker.patch("aocd.models.get_plugins", return_value=[ep])
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
    mocker.patch("aocd.models.get_plugins", return_value=[plug2, plug1])
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
    mocker.patch("aocd.models.get_plugins", return_value=[other_plug])
    puzzle = Puzzle(year=2018, day=1)
    with pytest.raises(AocdError("No entry point found for 'myplugin'")):
        puzzle.solve_for("myplugin")
    other_plug.load.assert_not_called()
    other_plug.load.return_value.assert_not_called()


def test_get_title_failure_no_heading(freezer, pook, caplog):
    freezer.move_to("2018-12-01 12:00:00Z")
    pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body="Advent of Code --- Day 1: hello ---",
    )
    puzzle = Puzzle(year=2018, day=1)
    with pytest.raises(AocdError("heading not found")):
        puzzle.title


def test_get_title_failure(freezer, pook, caplog):
    freezer.move_to("2018-12-01 12:00:00Z")
    pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body="Advent of Code <h2>--- Day 11: This SHOULD be day 1 ---</h2>",
    )
    puzzle = Puzzle(year=2018, day=1)
    msg = "unexpected h2 text: --- Day 11: This SHOULD be day 1 ---"
    with pytest.raises(AocdError(msg)):
        puzzle.title


def test_pprint(freezer, pook, mocker):
    freezer.move_to("2018-12-01 12:00:00Z")
    pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body="Advent of Code <h2>--- Day 1: The Puzzle Title ---</h2>",
    )
    puzzle = Puzzle(year=2018, day=1)
    assert puzzle.title == "The Puzzle Title"
    printer = mocker.MagicMock()
    puzzle._repr_pretty_(printer, cycle=False)
    [((pretty,), kwargs)] = printer.text.call_args_list
    assert not kwargs
    assert pretty.startswith("<Puzzle(2018, 1) at 0x")
    assert pretty.endswith(" - The Puzzle Title>")


def test_pprint_cycle(freezer, pook, mocker):
    freezer.move_to("2018-12-01 12:00:00Z")
    pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body="Advent of Code <h2>--- Day 1: The Puzzle Title ---</h2>",
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


def test_get_stats(pook):
    puzzle = Puzzle(year=2019, day=4)
    pook.get(
        url="https://adventofcode.com/2019/leaderboard/self",
        response_body=fake_stats_response,
    )
    stats = puzzle.my_stats
    assert stats == {
        "a": {"time": timedelta(minutes=3, seconds=30), "rank": 158, "score": 0},
        "b": {"time": timedelta(minutes=4, seconds=17), "rank": 25, "score": 76},
    }


def test_get_stats_when_token_expired(pook):
    # sadly, it just returns the global leaderboard, rather than a http 4xx
    user = User("token12345678")
    pook.get("https://adventofcode.com/2019/leaderboard/self", reply=302)
    with pytest.raises(DeadTokenError("the auth token ...5678 is dead")):
        user.get_stats(years=[2019])


def test_get_stats_when_no_stars_yet(pook):
    user = User("token12345678")
    pook.get(
        url="https://adventofcode.com/2019/leaderboard/self",
        response_body="<main>You haven't collected any stars... yet.</main>",
    )
    assert user.get_stats(years=[2019]) == {}


def test_get_stats_slow_user(pook):
    puzzle = Puzzle(year=2019, day=25)
    pook.get(
        url="https://adventofcode.com/2019/leaderboard/self",
        response_body=fake_stats_response,
    )
    stats = puzzle.my_stats
    assert stats == {
        "a": {"time": timedelta(hours=24), "rank": 2708, "score": 0},
        "b": {"time": timedelta(hours=24), "rank": 1926, "score": 0},
    }


def test_get_stats_fail(pook):
    puzzle = Puzzle(year=2019, day=13)
    pook.get(
        url="https://adventofcode.com/2019/leaderboard/self",
        response_body=fake_stats_response,
    )
    with pytest.raises(PuzzleUnsolvedError):
        puzzle.my_stats


def test_get_stats_partially_complete(pook):
    puzzle = Puzzle(year=2019, day=24)
    pook.get(
        url="https://adventofcode.com/2019/leaderboard/self",
        response_body=fake_stats_response,
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


def test_easter_eggs(pook):
    pook.get(
        url="https://adventofcode.com/2017/day/5",
        response_body=(
            "Advent of Code"
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


def test_get_stats_400(pook):
    url = "https://adventofcode.com/2015/leaderboard/self"
    pook.get(url, reply=400)
    user = User("testtoken")
    with pytest.raises(AocdError(f"HTTP 400 at {url}")):
        user.get_stats()


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_unsolved(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", side_effect=PuzzleUnsolvedError)
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_already_solved("one", "a")
    assert rv is None


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_empty(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_already_solved("one", "a")
    assert rv is None


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_saved_correct(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="one")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_already_solved("one", "a")
    assert rv == "Part a already solved with same answer: one"


@pytest.mark.answer_not_cached(install=False)
def test_check_guess_against_saved_incorrect(mocker):
    mocker.patch("aocd.models.Puzzle._get_answer", return_value="two")
    puzzle = Puzzle(year=2019, day=4)
    rv = puzzle._check_already_solved("one", "a")
    assert "Part a already solved with different answer: two" in rv


def test_owner_cache(aocd_config_dir):
    cache = aocd_config_dir / "token2id.json"
    cache.write_text('{"bleh": "a.u.n"}')
    user = User(token="bleh")
    user_id = user.id
    assert user_id == "a.u.n"
    assert str(user) == "<User a.u.n (token=...bleh)>"


def test_user_from_id(aocd_config_dir):
    cache = aocd_config_dir / "tokens.json"
    cache.write_text('{"github.testuser.123456":"testtoken"}')
    user = User.from_id("github.testuser.123456")
    assert user.token == "testtoken"


def test_user_from_unknown_id(aocd_config_dir):
    cache = aocd_config_dir / "tokens.json"
    cache.write_text('{"github.testuser.123456":"testtoken"}')
    with pytest.raises(UnknownUserError("User with id 'blah' is not known")):
        User.from_id("blah")


def test_examples_cache(aocd_data_dir, pook):
    mock = pook.get(
        url="https://adventofcode.com/2014/day/1",
        response_body=(
            "<title>Day 1 - Advent of Code 2014</title>"
            "<article><pre><code>1\n2\n3\n</code></pre><code>abc</code></article>"
            "<article><pre><code>1\n2\n3\n</code></pre><code>xyz</code></article>"
        ),
        times=1,
    )
    puzzle = Puzzle(day=1, year=2014)
    assert mock.calls == 0
    assert puzzle.examples[0].input_data == "1\n2\n3"
    assert mock.calls == 1
    assert puzzle.examples[0].input_data
    assert mock.calls == 1


def test_example_partial(aocd_data_dir, pook):
    # only one article, for example when part B isn't unlocked yet
    pook.get(
        url="https://adventofcode.com/2014/day/1",
        response_body=(
            "<title>Day 1 - Advent of Code 2014</title>"
            "<article><pre><code>1\n2\n3\n</code></pre><code>abc</code></article>"
        ),
    )
    puzzle = Puzzle(day=1, year=2014)
    [example] = puzzle.examples
    assert example.input_data == "1\n2\n3"
    assert example.answer_a == "abc"
    assert example.answer_b is None


def test_example_data_crash(pook, caplog):
    url = "https://adventofcode.com/2018/day/1"
    title_only = "<title>Day 1 - Advent of Code 2014</title>"
    pook.get(url, reply=200, response_body=title_only)
    puzzle = Puzzle(day=1, year=2018)
    assert not puzzle.examples
    err_repr = "ExampleParserError('no <article> found in html')"
    msg = f"unable to find example data for 2018/01 ({err_repr})"
    assert ("aocd.models", logging.WARNING, msg) in caplog.record_tuples


@pytest.mark.parametrize(
    "v_raw,v_expected,len_logs",
    [
        ("123", "123", 0),
        (123, "123", 0),
        ("xxx", "xxx", 0),
        (123.5, 123.5, 0),
        (123.0 + 123.0j, 123.0 + 123.0j, 0),
        (123.0, "123", 1),
        (123.0 + 0.0j, "123", 1),
        (np.int32(123), "123", 1),
        (np.uint32(123), "123", 1),
        (np.double(123.0), "123", 1),
        (np.complex64(123.0 + 0.0j), "123", 1),
        (np.complex64(123.0 + 0.5j), np.complex64(123.0 + 0.5j), 0),
    ],
)
def test_type_coercions(v_raw, v_expected, len_logs, caplog):
    p = Puzzle(2022, 1)
    v_actual = p._coerce_val(v_raw)
    assert v_actual == v_expected, f"{type(v_raw)} {v_raw})"
    assert len(caplog.records) == len_logs


def test_get_prose_cache(aocd_data_dir):
    cached = aocd_data_dir / "other-user-id" / "2022_01_prose.2.html"
    cached.parent.mkdir()
    cached.write_text("foo")
    puzzle = Puzzle(year=2022, day=1)
    assert puzzle._get_prose() == "foo"
    my_cached = aocd_data_dir / "testauth.testuser.000" / "2022_01_prose.2.html"
    my_cached.write_text("bar")
    assert puzzle._get_prose() == "bar"


def test_get_prose_fail(pook):
    url = "https://adventofcode.com/2018/day/1"
    pook.get(url, reply=400)
    puzzle = Puzzle(day=1, year=2018)
    with pytest.raises(AocdError("HTTP 400 at https://adventofcode.com/2018/day/1")):
        puzzle._get_prose()


def test_both_complete_on_day_25(pook):
    # we still parse the page even though both are complete but only one answer found
    pook.get(
        url="https://adventofcode.com/2018/day/25",
        response_body=(
            "Both parts of this puzzle are complete!"
            "<p>Your puzzle answer was <code>answerA</code></p>"
        ),
    )
    puzzle = Puzzle(day=25, year=2018)
    puzzle._get_prose()


def test_empty_response(pook):
    pook.get(url="https://adventofcode.com/2018/day/25")
    puzzle = Puzzle(day=25, year=2018)
    with pytest.raises(AocdError("Could not get prose for 2018/25")):
        puzzle._get_prose()


def test_unlock_time(pook):
    pook.get(url="https://adventofcode.com/2018/day/25")
    puzzle = Puzzle(day=13, year=2024)
    unlock_local = puzzle.unlock_time()
    unlock_aoctz = puzzle.unlock_time(local=False)
    expected = datetime(2024, 12, 13, 0, 0, 0, tzinfo=AOC_TZ)
    assert unlock_aoctz == unlock_local == expected


def test_all_puzzles(freezer):
    freezer.move_to("2017-10-10")
    all_puzzles = list(Puzzle.all())
    assert len(all_puzzles) == 50
    first, *rest, last = all_puzzles
    assert first.year == 2015
    assert first.day == 1
    assert last.year == 2016
    assert last.day == 25


def test_submit_prevents_bad_guesses_too_high(freezer, capsys, pook):
    freezer.move_to("2022-12-01 12:34:56-05:00")
    pook.get("https://adventofcode.com/2022/day/1", times=2)
    resp = "<article>That's not the right answer; your answer is too high</article>"
    pook.post("https://adventofcode.com/2022/day/1/answer", response_body=resp)
    puzzle = Puzzle(2022, 1)
    puzzle.answer_a = "1234"
    out, err = capsys.readouterr()
    assert not err
    assert "That's not the right answer; your answer is too high" in out
    puzzle.answer_a = "1235"
    out, err = capsys.readouterr()
    assert not err
    expected = """
        aocd will not submit that answer. At 2022-12-01 12:34:56-05:00 you've previously submitted 1234 and the server responded with:
        That's not the right answer; your answer is too high
        It is certain that '1235' is incorrect, because '1234' was too high.
    """
    for line in expected.splitlines():
        assert line.strip() in out


def test_submit_prevents_bad_guesses_too_low(freezer, capsys, pook):
    freezer.move_to("2022-12-01 12:34:56-05:00")
    pook.get("https://adventofcode.com/2022/day/1", times=2)
    resp = "<article>That's not the right answer; your answer is too low</article>"
    pook.post("https://adventofcode.com/2022/day/1/answer", response_body=resp)
    puzzle = Puzzle(2022, 1)
    puzzle.answer_a = "1234"
    out, err = capsys.readouterr()
    assert not err
    assert "That's not the right answer; your answer is too low" in out
    puzzle.answer_a = "foobar"
    out, err = capsys.readouterr()
    assert not err
    expected = """
        aocd will not submit that answer. At 2022-12-01 12:34:56-05:00 you've previously submitted 1234 and the server responded with:
        That's not the right answer; your answer is too low
        It is certain that 'foobar' is incorrect, because '1234' was too low.
    """
    for line in expected.splitlines():
        assert line.strip() in out


def test_submit_prevents_bad_guesses_known_incorrect(freezer, capsys, pook, mocker):
    mocker.patch("aocd.models.webbrowser.open")
    freezer.move_to("2022-12-01 12:34:56-05:00")
    pook.get("https://adventofcode.com/2022/day/1", times=2)
    resp = "<article>That's the right answer</article>"
    pook.post("https://adventofcode.com/2022/day/1/answer", response_body=resp)
    puzzle = Puzzle(2022, 1)
    puzzle.answer_a = "1234"
    out, err = capsys.readouterr()
    assert not err
    assert "That's the right answer" in out
    puzzle.answer_a = "4321"
    out, err = capsys.readouterr()
    assert not err
    expected = """
        aocd will not submit that answer. At 2022-12-01 12:34:56-05:00 you've previously submitted 1234 and the server responded with:
        That's the right answer
        It is certain that '4321' is incorrect, because '4321' != '1234'.
    """
    for line in expected.splitlines():
        assert line.strip() in out
