import pytest

from aocd.runner import _process_wrapper
from aocd.runner import format_time
from aocd.runner import main
from aocd.runner import run_for
from aocd.runner import run_one
from aocd.utils import colored


def test_no_plugins_avail(capsys, mocker):
    mock = mocker.patch("aocd.runner.get_plugins", return_value=[])
    mocker.patch("sys.argv", ["aoc"])
    msg = (
        "There are no plugins available. Install some package(s) with a registered 'adventofcode.user' entry-point.\n"
        "See https://github.com/wimglenn/advent-of-code-sample for an example plugin package structure.\n"
    )
    with pytest.raises(SystemExit(1)):
        main()
    out, err = capsys.readouterr()
    assert msg in err
    mock.assert_called_once_with()


def test_no_datasets_avail(capsys, mocker, aocd_config_dir):
    tokens_file = aocd_config_dir / "tokens.json"
    tokens_file.write_text("{}")
    mocker.patch("sys.argv", ["aoc"])
    msg = (
        "There are no datasets available to use.\n"
        f"Either export your AOC_SESSION or put some auth tokens into {tokens_file}\n"
    )
    with pytest.raises(SystemExit(1)):
        main()
    out, err = capsys.readouterr()
    assert msg in err


def test_main(capsys, mocker, aocd_config_dir):
    mock = mocker.patch("aocd.runner.run_for", return_value=0)
    ep1 = mocker.Mock()
    ep1.name = "user1"
    ep2 = mocker.Mock()
    ep2.name = "user2"
    mocker.patch("aocd.runner.get_plugins", return_value=[ep1, ep2])
    tokens_file = aocd_config_dir / "tokens.json"
    tokens_file.write_text('{"data1": "token1", "data2": "token2"}')
    mocker.patch("sys.argv", ["aoc", "--years=2015", "--days", "3", "7"])
    with pytest.raises(SystemExit(0)):
        main()
    mock.assert_called_once_with(
        plugs=["user1", "user2"],
        years=[2015],
        days=[3, 7],
        datasets={"data1": "token1", "data2": "token2"},
        example=False,
        timeout=60,
        autosubmit=True,
        reopen=False,
        capture=False,
    )


def fake_entry_point(year, day, data):
    assert year == 2015
    assert day == 1
    assert data == "testinput"
    return "answer1", "wrong"


def fake_entry_point_25(year, day, data):
    assert year == 2022
    assert day == 25
    assert data == "test example data"
    return "answer_a", ""


def xmas_entry_point(year, day, data):
    assert year == 2015
    assert day == 25
    assert data == "testinput"
    return "answer1", ""


def bugged_entry_point(year, day, data):
    raise Exception(123, 456)


def test_results(mocker, capsys):
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    fake_puzzle = mocker.MagicMock()
    fake_puzzle.year = 2015
    fake_puzzle.day = 1
    fake_puzzle.input_data = "testinput"
    fake_puzzle.answer_a = "answer1"
    fake_puzzle.answer_b = "answer2"
    fake_puzzle.title = "The Puzzle Title"
    mocker.patch("aocd.runner.Puzzle", return_value=fake_puzzle)
    run_for(
        plugs=["testuser"],
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


def test_results_xmas(mocker, capsys):
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = xmas_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    fake_puzzle = mocker.MagicMock(
        year=2015,
        day=25,
        input_data="testinput",
        answer_a="answer1",
        answer_b="not_used",
        title="The Puzzle Title",
    )
    mocker.patch("aocd.runner.Puzzle", return_value=fake_puzzle)
    run_for(
        plugs=["testuser"],
        years=[2015],
        days=[25],
        datasets={"testdataset": "testtoken"},
    )
    ep.load.assert_called_once_with()
    out, err = capsys.readouterr()
    txt = "2015/25 - The Puzzle Title                           testuser/testdataset"
    assert txt in out
    assert "part a: answer1 " in out
    assert "part b" not in out
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
    run_for(plugs=[], years=[], days=[], datasets=[])


def test_day_out_of_range(mocker, capsys, freezer):
    freezer.move_to("2018-12-01 12:00:00Z")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    run_for(
        plugs=["testuser"],
        years=[2018],
        days=[27],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    assert out == err == ""


def test_run_error(aocd_data_dir, mocker, capsys):
    prose_dir = aocd_data_dir / "prose"
    prose_dir.mkdir()
    puzzle_file = prose_dir / "2018_25_prose.0.html"
    puzzle_file.write_text("<h2>--- Day 25: The Puzzle Title ---</h2>")
    input_path = aocd_data_dir / "testauth.testuser.000" / "2018_25_input.txt"
    input_path.write_text("someinput")
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2018_25a_answer.txt"
    answer_path.write_text("answ")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = bugged_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    run_for(
        plugs=["testuser"],
        years=[2018],
        days=[25],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    txt = "Exception(123, 456)"
    assert "✖" in out
    assert txt in out
    assert "part b" not in out  # because it's 25 dec, no part b puzzle


def test_run_and_autosubmit(aocd_data_dir, mocker, capsys, pook):
    prose_dir = aocd_data_dir / "prose"
    prose_dir.mkdir()
    puzzle_file = prose_dir / "2015_01_prose.0.html"
    puzzle_file.write_text("<h2>--- Day 1: The Puzzle Title ---</h2>")
    input_path = aocd_data_dir / "testauth.testuser.000" / "2015_01_input.txt"
    input_path.write_text("testinput")
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2015_01a_answer.txt"
    answer_path.write_text("answer1")
    pook.get(url="https://adventofcode.com/2015/day/1", times=2)
    pook.post(
        url="https://adventofcode.com/2015/day/1/answer",
        response_body="<article>That's not the right answer</article>",
    )
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    run_for(
        plugs=["testuser"],
        years=[2015],
        days=[1],
        datasets={"default": "thetesttoken"},
    )
    out, err = capsys.readouterr()
    assert "part a: answer1 " in out
    assert "part b: wrong (correct answer unknown)" in out


def test_run_and_no_autosubmit(aocd_data_dir, mocker, capsys, pook):
    prose_dir = aocd_data_dir / "prose"
    prose_dir.mkdir()
    puzzle_file = prose_dir / "2015_01_prose.0.html"
    puzzle_file.write_text("<h2>--- Day 1: The Puzzle Title ---</h2>")
    input_path = aocd_data_dir / "testauth.testuser.000" / "2015_01_input.txt"
    input_path.write_text("testinput")
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2015_01a_answer.txt"
    answer_path.write_text("answer1")
    pook.get(url="https://adventofcode.com/2015/day/1")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    run_for(
        plugs=["testuser"],
        years=[2015],
        days=[1],
        datasets={"default": "thetesttoken"},
        autosubmit=False,
    )
    out, err = capsys.readouterr()
    assert "part a: answer1 " in out
    assert "part b: wrong (correct answer unknown)" in out


def test_run_against_examples(aocd_data_dir, mocker, capsys, pook):
    prose_dir = aocd_data_dir / "prose"
    prose_dir.mkdir()
    puzzle_file = prose_dir / "2022_25_prose.0.html"
    puzzle_file.write_text(
        """
        <title>Day 25 - Advent of Code 2022</title>
        <h2>--- Day 25: The Puzzle Title ---</h2>
        <article>
        <pre>test example data</pre>
        <code>test answer_a</code>
        </article>
        """
    )
    pook.get(url="https://adventofcode.com/2022/day/25")
    ep = mocker.Mock()
    ep.name = "testuser"
    ep.load.return_value = fake_entry_point_25
    mocker.patch("aocd.runner.get_plugins", return_value=[ep])
    run_for(
        plugs=["testuser"],
        years=[2022],
        days=[25],
        datasets={"default": "thetesttoken"},
        example=True,
    )
    out, err = capsys.readouterr()
    assert "2022/25 - The Puzzle Title" in out
    assert " testuser/example-1 " in out
    assert "part a: answer_a" in out
    assert "part b:" not in out


def file_entry_point(year, day, data):
    assert year == 2015
    assert day == 1
    assert data == "abcxyz"
    with open("input.txt") as f:
        assert f.read() == "abcxyz"
    return 123, "456"


def test_load_input_from_file(mocker):
    ep = mocker.Mock()
    ep.name = "file_ep_user"
    ep.load.return_value = file_entry_point
    a, b, walltime, error = run_one(2015, 1, "abcxyz", ep)
    assert a == "123"
    assert b == "456"
    assert 0 < walltime < 60
    assert not error


def test_scratch_cleanup_failure(mocker):
    ep = mocker.Mock()
    ep.name = "file_ep_user"
    ep.load.return_value = file_entry_point
    mocker.patch("os.rmdir", side_effect=OSError)
    run_one(2015, 1, "abcxyz", ep)


def test_process_wrapper(capsys):
    _process_wrapper(lambda: print("1"))
    out, err = capsys.readouterr()
    assert err == ""
    assert out.strip() == "1"
    _process_wrapper(lambda: print("2"), capture=True)
    out, err = capsys.readouterr()
    assert not err and not out
