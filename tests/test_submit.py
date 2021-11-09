import errno

import pytest
from termcolor import colored

from aocd.exceptions import AocdError
from aocd.post import submit
from aocd.utils import _ensure_intermediate_dirs


def test_submit_correct_answer(requests_mock, capsys):
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer. Yeah!!</article>",
    )
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=False)
    assert post.called
    assert post.call_count == 1
    query = sorted(post.last_request.text.split("&"))  # form encoded
    assert query == ["answer=1234", "level=1"]
    out, err = capsys.readouterr()
    msg = colored("That's the right answer. Yeah!!", "green")
    assert msg in out


def test_correct_submit_reopens_browser_on_answer_page(mocker, requests_mock):
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    browser_open = mocker.patch("webbrowser.open")
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=True)
    browser_open.assert_called_once_with("https://adventofcode.com/2018/day/1#part2")


def test_submit_bogus_part():
    with pytest.raises(AocdError('part must be "a" or "b"')):
        submit(1234, part="c")


def test_server_error(requests_mock, freezer):
    freezer.move_to("2018-12-01 12:00:00Z")
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer", status_code=500
    )
    with pytest.raises(AocdError("Non-200 response for POST: <Response [500]>")):
        submit(1234, part="a")


def test_submit_when_already_solved(requests_mock, capsys):
    html = """<article><p>You don't seem to be solving the right level.  Did you already complete it? <a href="/2018/day/1">[Return to Day 1]</a></p></article>"""
    requests_mock.post(url="https://adventofcode.com/2018/day/1/answer", text=html)
    submit(1234, part="a", year=2018, day=1, reopen=False)
    out, err = capsys.readouterr()
    msg = "You don't seem to be solving the right level.  Did you already complete it? [Return to Day 1]"
    msg = colored(msg, "yellow")
    assert msg in out


def test_submitted_too_recently_autoretry(requests_mock, capsys, mocked_sleep):
    html1 = """<article><p>You gave an answer too recently; you have to wait after submitting an answer before trying again.  You have 30s left to wait. <a href="/2015/day/24">[Return to Day 24]</a></p></article>"""
    html2 = "<article>That's the right answer. Yeah!!</article>"
    requests_mock.post(
        "https://adventofcode.com/2015/day/24/answer",
        [{"text": html1}, {"text": html2}],
    )
    submit(1234, part="a", year=2015, day=24, reopen=False)
    mocked_sleep.assert_called_once_with(30)
    out, err = capsys.readouterr()
    msg = "That's the right answer. Yeah!!"
    msg = colored(msg, "green")
    assert msg in out


def test_submitted_too_recently_autoretry_quiet(requests_mock, capsys, mocked_sleep):
    html1 = """<article><p>You gave an answer too recently; you have to wait after submitting an answer before trying again.  You have 3m 30s left to wait. <a href="/2015/day/24">[Return to Day 24]</a></p></article>"""
    html2 = "<article>That's the right answer. Yeah!!</article>"
    requests_mock.post(
        "https://adventofcode.com/2015/day/24/answer",
        [{"text": html1}, {"text": html2}],
    )
    submit(1234, part="a", year=2015, day=24, reopen=False, quiet=True)
    mocked_sleep.assert_called_once_with(3 * 60 + 30)
    out, err = capsys.readouterr()
    assert out == err == ""


def test_submit_when_submitted_too_recently_no_autoretry(requests_mock, capsys):
    html = """<article><p>You gave an answer too recently</p></article>"""
    requests_mock.post(url="https://adventofcode.com/2015/day/25/answer", text=html)
    submit(1234, part="a", year=2015, day=25, reopen=False)
    out, err = capsys.readouterr()
    msg = "You gave an answer too recently"
    msg = colored(msg, "red")
    assert msg in out


def test_submit_wrong_answer(requests_mock, capsys):
    html = """<article><p>That's not the right answer.  If you're stuck, there are some general tips on the <a href="/2015/about">about page</a>, or you can ask for hints on the <a href="https://www.reddit.com/r/adventofcode/" target="_blank">subreddit</a>.  Please wait one minute before trying again. (You guessed <span style="white-space:nowrap;"><code>WROOOONG</code>.)</span> <a href="/2015/day/1">[Return to Day 1]</a></p></article>"""
    requests_mock.post(url="https://adventofcode.com/2015/day/1/answer", text=html)
    submit(1234, part="a", year=2015, day=1, reopen=False)
    out, err = capsys.readouterr()
    msg = "That's not the right answer.  If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit.  Please wait one minute before trying again. (You guessed WROOOONG.) [Return to Day 1]"
    msg = colored(msg, "red")
    assert msg in out


def test_correct_submit_records_good_answer(requests_mock, aocd_data_dir):
    requests_mock.get(url="https://adventofcode.com/2018/day/1")
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    answer_fname = aocd_data_dir / "testauth.testuser.000/2018_01b_answer.txt"
    assert not answer_fname.exists()
    submit(1234, part="b", day=1, year=2018, session="whatever", reopen=False)
    assert answer_fname.exists()
    assert answer_fname.read_text() == "1234"


def test_submit_correct_part_a_answer_for_part_b_blocked(requests_mock):
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text="<h2>Day 1: Yo Dawg</h2> <p>Your puzzle answer was <code>1234</code></p>",
    )
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    with pytest.raises(AocdError("cowardly refusing to re-submit answer_a (1234) for part b")):
        submit(1234, part="b", day=1, year=2018, session="whatever", reopen=False)


def test_submits_for_partb_when_already_submitted_parta(freezer, requests_mock, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000/2018_01a_answer.txt"
    parta_answer.touch()
    submit(1234, reopen=False)
    assert post.called
    assert post.call_count == 1
    query = sorted(post.last_request.text.split("&"))  # form encoded
    assert query == ["answer=1234", "level=2"]


def test_submit_when_parta_solved_but_answer_unsaved(freezer, requests_mock,
                                                     aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text="<h2>Day 1: Yo Dawg</h2> <p>Your puzzle answer was <code>666</code></p>",
    )
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01a_answer.txt"
    partb_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01b_answer.txt"
    assert not parta_answer.exists()
    assert not partb_answer.exists()
    submit(1234, reopen=False)
    assert parta_answer.exists()
    assert partb_answer.exists()
    assert parta_answer.read_text() == "666"
    assert partb_answer.read_text() == "1234"
    title_path = aocd_data_dir / "titles" / "2018_01.txt"
    assert title_path.read_text() == "Yo Dawg\n"
    assert get.call_count == 1
    assert post.call_count == 1
    query = sorted(post.last_request.text.split("&"))  # form encoded
    assert query == ["answer=1234", "level=2"]


def test_submit_saves_both_answers_if_possible(freezer, requests_mock, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = requests_mock.get(
        url="https://adventofcode.com/2018/day/1",
        text=(
            "<p>Your puzzle answer was <code>answerA</code></p>"
            "<p>Your puzzle answer was <code>answerB</code></p>"
        ),
    )
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer", text="<article></article>"
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000/2018_01a_answer.txt"
    partb_answer = aocd_data_dir / "testauth.testuser.000/2018_01b_answer.txt"
    assert not parta_answer.exists()
    assert not partb_answer.exists()
    submit("answerB", reopen=False)
    assert parta_answer.exists()
    assert partb_answer.exists()
    assert parta_answer.read_text() == "answerA"
    assert partb_answer.read_text() == "answerB"
    assert get.call_count == 1
    assert post.call_count == 1
    query = sorted(post.last_request.text.split("&"))  # form encoded
    assert query == ["answer=answerB", "level=2"]


def test_submit_puts_level1_by_default(freezer, requests_mock, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = requests_mock.get(url="https://adventofcode.com/2018/day/1")
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000/2018_01a_answer.txt"
    assert not parta_answer.exists()
    submit(1234, reopen=False)
    assert get.called
    assert get.call_count == 1
    assert post.called
    assert post.call_count == 1
    query = sorted(post.last_request.text.split("&"))  # form encoded
    assert query == ["answer=1234", "level=1"]
    assert parta_answer.exists()
    assert parta_answer.read_text() == "1234"


def test_failure_to_create_dirs_unhandled(mocker):
    mocker.patch("os.makedirs", side_effect=TypeError)
    with pytest.raises(TypeError):
        _ensure_intermediate_dirs("/")
    mocker.patch("os.makedirs", side_effect=[TypeError, OSError])
    with pytest.raises(OSError):
        _ensure_intermediate_dirs("/")
    err = OSError()
    err.errno = errno.EEXIST
    mocker.patch("os.makedirs", side_effect=[TypeError, err])
    _ensure_intermediate_dirs("/")


def test_cannot_submit_same_bad_answer_twice(requests_mock, capsys):
    mock = requests_mock.post(
        url="https://adventofcode.com/2015/day/1/answer",
        text="<article><p>That's not the right answer. (You guessed <span>69.)</span></a></p></article>",
    )
    submit(year=2015, day=1, part="a", answer=69)
    submit(year=2015, day=1, part="a", answer=69)
    submit(year=2015, day=1, part="a", answer=69, quiet=True)
    assert mock.call_count == 1
    out, err = capsys.readouterr()
    assert "aocd will not submit that answer again" in out


def test_will_not_submit_null():
    with pytest.raises(AocdError("cowardly refusing to submit non-answer: None")):
        submit(None, part="a")


@pytest.mark.answer_not_cached(rv='value')
def test_submit_guess_against_saved(requests_mock, capsys):
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer. Yeah!!</article>",
    )
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=False)
    assert post.call_count == 0
