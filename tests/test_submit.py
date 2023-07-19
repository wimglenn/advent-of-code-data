import json
import logging

import pytest

from aocd.exceptions import AocdError
from aocd.post import submit
from aocd.utils import colored


def test_submit_correct_answer(pook, capsys):
    post = pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        content="application/x-www-form-urlencoded",
        body="level=1&answer=1234",
        response_body="<article>That's the right answer. Yeah!!</article>",
    )
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=False)
    assert post.calls == 1
    out, err = capsys.readouterr()
    msg = colored("That's the right answer. Yeah!!", "green")
    assert msg in out


def test_correct_submit_reopens_browser_on_answer_page(mocker, pook):
    pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        response_body="<article>That's the right answer</article>",
    )
    browser_open = mocker.patch("aocd.models.webbrowser.open")
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=True)
    browser_open.assert_called_once_with("https://adventofcode.com/2018/day/1#part2")


def test_submit_bogus_part():
    with pytest.raises(AocdError('part must be "a" or "b"')):
        submit(1234, part="c")


def test_server_error(pook, freezer):
    url = "https://adventofcode.com/2018/day/1/answer"
    freezer.move_to("2018-12-01 12:00:00Z")
    pook.post(url, reply=500)
    with pytest.raises(AocdError(f"HTTP 500 at {url}")):
        submit(1234, part="a")


def test_submit_when_already_solved(pook, capsys):
    html = """<article><p>You don't seem to be solving the right level.  Did you already complete it? <a href="/2018/day/1">[Return to Day 1]</a></p></article>"""
    pook.post(url="https://adventofcode.com/2018/day/1/answer", response_body=html)
    submit(1234, part="a", year=2018, day=1, reopen=False)
    out, err = capsys.readouterr()
    msg = "You don't seem to be solving the right level.  Did you already complete it? [Return to Day 1]"
    msg = colored(msg, "yellow")
    assert msg in out


def test_submitted_too_recently_autoretry(pook, capsys, mocked_sleep):
    html1 = """<article><p>You gave an answer too recently; you have to wait after submitting an answer before trying again.  You have 30s left to wait. <a href="/2015/day/24">[Return to Day 24]</a></p></article>"""
    html2 = "<article>That's the right answer. Yeah!!</article>"
    for body in html1, html2:
        pook.post(
            "https://adventofcode.com/2015/day/24/answer",
            response_body=body,
        )
    submit(1234, part="a", year=2015, day=24, reopen=False)
    mocked_sleep.assert_called_once_with(30)
    out, err = capsys.readouterr()
    msg = "That's the right answer. Yeah!!"
    msg = colored(msg, "green")
    assert msg in out


def test_submitted_too_recently_autoretry_quiet(pook, capsys, mocked_sleep):
    html1 = """<article><p>You gave an answer too recently; you have to wait after submitting an answer before trying again.  You have 3m 30s left to wait. <a href="/2015/day/24">[Return to Day 24]</a></p></article>"""
    html2 = "<article>That's the right answer. Yeah!!</article>"
    for body in html1, html2:
        pook.post(
            "https://adventofcode.com/2015/day/24/answer",
            response_body=body,
        )
    submit(1234, part="a", year=2015, day=24, reopen=False, quiet=True)
    mocked_sleep.assert_called_once_with(3 * 60 + 30)
    out, err = capsys.readouterr()
    assert out == err == ""


def test_submit_when_submitted_too_recently_no_autoretry(pook, capsys):
    html = """<article><p>You gave an answer too recently</p></article>"""
    pook.post(url="https://adventofcode.com/2015/day/25/answer", response_body=html)
    submit(1234, part="a", year=2015, day=25, reopen=False)
    out, err = capsys.readouterr()
    msg = "You gave an answer too recently"
    msg = colored(msg, "red")
    assert msg in out


def test_submit_wrong_answer(pook, capsys):
    html = """<article><p>That's not the right answer.  If you're stuck, there are some general tips on the <a href="/2015/about">about page</a>, or you can ask for hints on the <a href="https://www.reddit.com/r/adventofcode/" target="_blank">subreddit</a>.  Please wait one minute before trying again. (You guessed <span style="white-space:nowrap;"><code>WROOOONG</code>.)</span> <a href="/2015/day/1">[Return to Day 1]</a></p></article>"""
    pook.post(url="https://adventofcode.com/2015/day/1/answer", response_body=html)
    submit(1234, part="a", year=2015, day=1, reopen=False)
    out, err = capsys.readouterr()
    msg = "That's not the right answer.  If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit.  Please wait one minute before trying again. (You guessed WROOOONG.) [Return to Day 1]"
    msg = colored(msg, "red")
    assert msg in out


def test_correct_submit_records_good_answer(pook, aocd_data_dir):
    pook.get(url="https://adventofcode.com/2018/day/1")
    pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        response_body="<article>That's the right answer</article>",
    )
    answer_path = aocd_data_dir / "testauth.testuser.000" / "2018_01b_answer.txt"
    assert not answer_path.exists()
    submit(1234, part="b", day=1, year=2018, session="whatever", reopen=False)
    assert answer_path.exists()
    assert answer_path.read_text() == "1234"


def test_submit_correct_part_a_answer_for_part_b_blocked(pook):
    pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body=(
            "<h2>--- Day 1: Yo Dawg ---</h2>"
            "The first half of this puzzle is complete!"
            "<p>Your puzzle answer was <code>1234</code></p>"
        ),
    )
    pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        response_body="<article>That's the right answer</article>",
    )
    expected_msg = "cowardly refusing to submit 1234 for part b, because that was the answer for part a"
    with pytest.raises(AocdError(expected_msg)):
        submit(1234, part="b", day=1, year=2018, session="whatever", reopen=False)


def test_submits_for_partb_when_already_submitted_parta(freezer, pook, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    post = pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        body="level=2&answer=1234",
        response_body="<article>That's the right answer</article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01a_answer.txt"
    parta_answer.touch()
    submit(1234, reopen=False)
    assert post.calls == 1


def test_submit_when_parta_solved_but_answer_unsaved(freezer, pook, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body=(
            "<h2>--- Day 1: Yo Dawg ---</h2>"
            "The first half of this puzzle is complete!"
            "<p>Your puzzle answer was <code>666</code></p>"
        ),
    )
    post = pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        body="level=2&answer=1234",
        response_body="<article>That's the right answer</article>",
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
    assert get.calls == 1
    assert post.calls == 1
    prose_path = aocd_data_dir / "testauth.testuser.000" / "2018_01_prose.1.html"
    assert prose_path.is_file()
    assert " Yo Dawg " in prose_path.read_text()


def test_submit_saves_both_answers_if_possible(freezer, pook, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = pook.get(
        url="https://adventofcode.com/2018/day/1",
        response_body=(
            "Both parts of this puzzle are complete!"
            "<p>Your puzzle answer was <code>answerA</code></p>"
            "<p>Your puzzle answer was <code>answerB</code></p>"
        ),
    )
    post = pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        body="level=2&answer=answerB",
        response_body="<article></article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01a_answer.txt"
    partb_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01b_answer.txt"
    assert not parta_answer.exists()
    assert not partb_answer.exists()
    submit("answerB", reopen=False)
    assert parta_answer.exists()
    assert partb_answer.exists()
    assert parta_answer.read_text() == "answerA"
    assert partb_answer.read_text() == "answerB"
    assert get.calls == 1
    assert post.calls == 1


def test_submit_puts_level1_by_default(freezer, pook, aocd_data_dir):
    freezer.move_to("2018-12-01 12:00:00Z")
    get = pook.get(url="https://adventofcode.com/2018/day/1")
    post = pook.post(
        url="https://adventofcode.com/2018/day/1/answer",
        body="level=1&answer=1234",
        response_body="<article>That's the right answer</article>",
    )
    parta_answer = aocd_data_dir / "testauth.testuser.000" / "2018_01a_answer.txt"
    assert not parta_answer.exists()
    submit(1234, reopen=False)
    assert get.calls == 1
    assert post.calls == 1
    assert parta_answer.exists()
    assert parta_answer.read_text() == "1234"


def test_cannot_submit_same_bad_answer_twice(aocd_data_dir, pook, capsys, freezer):
    mock1 = pook.post(
        url="https://adventofcode.com/2015/day/1/answer",
        response_body="<article><p>That's not the right answer. (You guessed <span>69.)</span></a></p></article>",
    )
    mock2 = pook.post(
        url="https://adventofcode.com/2015/day/1/answer",
        response_body="<article><p>That's not the right answer idiot. (You guessed <span>70.)</span></a></p></article>",
    )
    freezer.move_to("2015-12-01 00:00:01-05:00")
    submit(year=2015, day=1, part="a", answer=69, quiet=True)
    freezer.move_to("2015-12-01 00:00:31-05:00")
    submit(year=2015, day=1, part="a", answer=70, quiet=True)
    submit(year=2015, day=1, part="a", answer=69)
    assert mock1.calls == 1
    assert mock2.calls == 1
    out, err = capsys.readouterr()
    cached = aocd_data_dir / "testauth.testuser.000" / "2015_01_post.json"
    assert "aocd will not submit that answer again" in out
    data = json.loads(cached.read_text())
    assert data == [
        {
            "part": "a",
            "value": "69",
            "when": "2015-12-01 00:00:01-05:00",
            "message": "That's not the right answer. (You guessed 69.)",
        },
        {
            "part": "a",
            "value": "70",
            "when": "2015-12-01 00:00:31-05:00",
            "message": "That's not the right answer idiot. (You guessed 70.)",
        },
    ]


def test_will_not_submit_null():
    with pytest.raises(AocdError("cowardly refusing to submit non-answer: None")):
        submit(None, part="a")


@pytest.mark.answer_not_cached(rv="value")
def test_submit_guess_against_saved(pook, capsys):
    post = pook.post(url="https://adventofcode.com/2018/day/1/answer")
    submit(1234, part="a", day=1, year=2018, session="whatever", reopen=False)
    assert post.calls == 0


def test_submit_float_warns(pook, capsys, caplog):
    post = pook.post(
        url="https://adventofcode.com/2022/day/8/answer",
        response_body="<article>yeah</article>",
    )
    submit(1234.0, part="a", day=8, year=2022, session="whatever", reopen=False)
    assert post.calls == 1
    record = ("aocd.models", logging.WARNING, "coerced float value 1234.0 for 2022/08")
    assert record in caplog.record_tuples
