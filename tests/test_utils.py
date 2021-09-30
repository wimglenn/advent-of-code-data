import platform
import pytest
from aocd.exceptions import DeadTokenError
from aocd.utils import blocker
from aocd.utils import get_owner
from freezegun import freeze_time


cpython = platform.python_implementation() == "CPython"


@pytest.mark.xfail(not cpython, reason="freezegun tick is not working on pypy")
def test_blocker(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", tick=True):
        # 0.2 second before unlock day 1
        blocker(dt=0.2)
    out, err = capsys.readouterr()
    assert " Unlock day 1 at " in out


@pytest.mark.xfail(not cpython, reason="freezegun auto-tick is not working on pypy either")
def test_blocker_quiet(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", auto_tick_seconds=1):
        blocker(dt=0.2, quiet=True)
    out, err = capsys.readouterr()
    assert not out


def test_get_owner_not_logged_in(requests_mock):
    requests_mock.get("https://adventofcode.com/settings", status_code=302)
    with pytest.raises(DeadTokenError):
        get_owner("not_logged_in")


def test_get_owner(requests_mock):
    requests_mock.get("https://adventofcode.com/settings", text="<code>123-456-9c3a0172</code>")
    owner = get_owner("not_logged_in")
    assert owner == "unknown.unknown.123"
