import platform
import pytest
from aocd.utils import blocker
from freezegun import freeze_time


cpython = platform.python_implementation() == "CPython"


# 0.2 second before unlock day 1
@pytest.mark.xfail(not cpython, reason="freezegun auto-tick is not working on pypy")
@freeze_time("2020-11-30 23:59:59.8-05:00", tick=True)
def test_blocker(capsys):
    blocker(dt=0.2)
    out, err = capsys.readouterr()
    assert " Unlock day 1 at " in out


@pytest.mark.xfail(not cpython, reason="freezegun auto-tick is not working on pypy")
@freeze_time("2020-11-30 23:59:59.8-05:00", auto_tick_seconds=1)
def test_blocker_quiet(capsys):
    blocker(dt=0.2, quiet=True)
    out, err = capsys.readouterr()
    assert not out
