import pytest

from aocd.get import get_cookie
from aocd.exceptions import AocdError


def test_no_session_id(test_token, capsys):
    test_token.remove()
    with pytest.raises(AocdError("Missing session ID")):
        get_cookie()
    out, err = capsys.readouterr()
    assert out == ""
    assert "ERROR: AoC session ID is needed to get your puzzle data!" in err


def test_get_session_id_from_env(monkeypatch):
    monkeypatch.setenv("AOC_SESSION", "tokenfromenv1")
    token = get_cookie()
    assert token == "tokenfromenv1"


def test_get_session_id_from_file(test_token):
    test_token.write("tokenfromfile")
    token = get_cookie()
    assert token == "tokenfromfile"


def test_env_takes_priority_over_file(monkeypatch, test_token):
    monkeypatch.setenv("AOC_SESSION", "tokenfromenv2")
    token = get_cookie()
    assert token == "tokenfromenv2"


def test_problem_loading_session_id_is_left_unhandled(test_token):
    test_token.remove()
    test_token.ensure_dir()
    with pytest.raises(IOError):
        get_cookie()
