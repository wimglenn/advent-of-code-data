import pytest

from aocd.exceptions import AocdError
from aocd.models import default_user


def test_no_session_id(test_token, capsys):
    test_token.unlink()
    with pytest.raises(AocdError("Missing session ID")):
        default_user()
    out, err = capsys.readouterr()
    assert out == ""
    assert "ERROR: AoC session ID is needed to get your puzzle data!" in err


def test_get_session_id_from_env(monkeypatch):
    monkeypatch.setenv("AOC_SESSION", "tokenfromenv1")
    user = default_user()
    assert user.token == "tokenfromenv1"


def test_get_session_id_from_file(test_token):
    test_token.write_text("tokenfromfile")
    user = default_user()
    assert user.token == "tokenfromfile"


def test_env_takes_priority_over_file(monkeypatch, test_token):
    monkeypatch.setenv("AOC_SESSION", "tokenfromenv2")
    user = default_user()
    assert user.token == "tokenfromenv2"


def test_problem_loading_session_id_is_left_unhandled(test_token):
    test_token.unlink()
    test_token.mkdir()
    with pytest.raises(OSError):
        default_user()
