import pytest
from termcolor import colored

import aocd
from aocd import AocdError


submit = aocd._module.submit


def test_submit_correct_answer(requests_mock, capsys):
    post = requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer. Yeah!!</article>",
    )
    submit(1234, level=1, day=1, year=2018, session="whatever", reopen=False)
    assert post.called
    assert post.call_count == 1
    assert post.last_request.text == 'answer=1234&level=1'
    out, err = capsys.readouterr()
    msg = colored("That's the right answer. Yeah!!", "green")
    assert msg in out


def test_correct_submit_reopens_browser_on_answer_page(mocker, requests_mock):
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    browser_open = mocker.patch("aocd._module.webbrowser.open")
    submit(1234, level=1, day=1, year=2018, session="whatever", reopen=True)
    browser_open.assert_called_once_with("https://adventofcode.com/2018/day/1/answer")


def test_submit_bogus_level():
    with pytest.raises(AocdError("level must be 1 or 2")):
        submit(1234, level=3)


def test_server_error(requests_mock, freezer):
    freezer.move_to("2018-12-01 12:00:00Z")
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        status_code=500,
    )
    with pytest.raises(AocdError("Non-200 response for POST: <Response [500]>")):
        submit(1234, level=1)


def test_submit_when_already_solved(requests_mock, capsys):
    html = '''<article><p>You don't seem to be solving the right level.  Did you already complete it? <a href="/2018/day/1">[Return to Day 1]</a></p></article>'''
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text=html,
    )
    submit(1234, level=1, year=2018, day=1, reopen=False)
    out, err = capsys.readouterr()
    msg = "You don't seem to be solving the right level.  Did you already complete it? [Return to Day 1]"
    msg = colored(msg, "yellow")
    assert msg in out


def test_correct_submit_records_good_answer(requests_mock, tmpdir):
    requests_mock.post(
        url="https://adventofcode.com/2018/day/1/answer",
        text="<article>That's the right answer</article>",
    )
    answer_fname = tmpdir / ".config/aocd/whatever/2018/1b_answer.txt"
    assert not answer_fname.exists()
    submit(1234, level=2, day=1, year=2018, session="whatever", reopen=False)
    assert answer_fname.exists()
    assert answer_fname.read() == "1234"


def test_failure_to_create_dirs_unhandled():
    with pytest.raises(OSError):
        aocd._module._ensure_intermediate_dirs("/")
