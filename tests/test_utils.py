import platform

import pytest
from freezegun import freeze_time

from aocd.exceptions import DeadTokenError
from aocd.utils import atomic_write_file
from aocd.utils import blocker
from aocd.utils import get_owner


cpython = platform.python_implementation() == "CPython"


@pytest.mark.xfail(not cpython, reason="freezegun tick is not working on pypy")
def test_blocker(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", tick=True):
        # 0.2 second before unlock day 1
        blocker(dt=0.2)
    out, err = capsys.readouterr()
    assert " Unlock day 1 at " in out


def test_blocker_quiet(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", auto_tick_seconds=1):
        blocker(dt=0.2, quiet=True)
    out, err = capsys.readouterr()
    assert not out


def test_get_owner_not_logged_in(pook):
    pook.reset()
    pook.get("https://adventofcode.com/settings", reply=302)
    with pytest.raises(DeadTokenError):
        get_owner("not_logged_in")


def test_get_owner_user_id(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body="<span>Link to wtf</span><code>ownerproof-123-456-9c3a0172</code>",
    )
    owner = get_owner("...")
    assert owner == "unknown.unknown.123"


def test_get_owner_and_username(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body="<span>Link to https://www.reddit.com/u/wim</span><code>ownerproof-123-456-9c3a0172</code>",
    )
    owner = get_owner("...")
    assert owner == "reddit.wim.123"


def test_get_owner_google(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body='<span><img src="https://lh3.googleusercontent.com/...">wim</span><code>ownerproof-1-2</code>',
    )
    owner = get_owner("...")
    assert owner == "google.wim.1"


def test_atomic_write_file(aocd_data_dir):
    target = aocd_data_dir / "foo" / "bar" / "baz.txt"
    atomic_write_file(target, "123")  # no clobber
    assert target.read_text() == "123"
    atomic_write_file(target, "456")  # clobber existing
    assert target.read_text() == "456"
