import io
import logging
import os
import threading
from importlib.metadata import version

import pytest

import aocd
from aocd.exceptions import AocdError
from aocd.exceptions import PuzzleLockedError


def test_get_from_server(pook):
    mock = pook.get(
        url="https://adventofcode.com/2018/day/1/input",
        response_body="fake data for year 2018 day 1",
    )
    data = aocd.get_data(year=2018, day=1)
    assert data == "fake data for year 2018 day 1"
    assert mock.calls == 1


def test_get_from_server_has_error(pook):
    url = "https://adventofcode.com/2018/day/1/input"
    pook.get(url, reply=418)
    with pytest.raises(AocdError(f"HTTP 418 at {url}")):
        aocd.get_data(year=2018, day=1, session="bogus")


def test_get_data_uses_current_date_if_unspecified(pook, freezer):
    mock = pook.get(
        url="https://adventofcode.com/2017/day/17/input",
        response_body="fake data for year 2017 day 17",
    )
    freezer.move_to("2017-12-17 12:00:00Z")
    data = aocd.get_data()
    assert data == "fake data for year 2017 day 17"
    assert mock.calls == 1


def test_saved_data_is_reused_if_available(aocd_data_dir, pook):
    mock = pook.get(
        url="https://adventofcode.com/2018/day/1/input",
        response_body="fake data for year 2018 day 1",
    )
    cached = aocd_data_dir / "testauth.testuser.000/2018_01_input.txt"
    cached.touch()
    cached.write_text("saved data for year 2018 day 1")
    data = aocd.get_data(year=2018, day=1)
    assert data == "saved data for year 2018 day 1"
    assert mock.calls == 0


def test_server_error(pook, caplog):
    url = "https://adventofcode.com/2101/day/1/input"
    mock = pook.get(
        url=url,
        response_body="AWS meltdown",
        reply=500,
    )
    with pytest.raises(AocdError(f"HTTP 500 at {url}")):
        aocd.get_data(year=2101, day=1)
    assert mock.calls == 1
    assert caplog.record_tuples == [
        ("aocd.models", logging.ERROR, "got 500 status code token=...oken"),
        ("aocd.models", logging.ERROR, "AWS meltdown"),
    ]


def test_puzzle_not_available_yet(pook, caplog):
    mock = pook.get(
        url="https://adventofcode.com/2101/day/1/input",
        response_body="Not Found",
        reply=404,
    )
    with pytest.raises(PuzzleLockedError("2101/01 not available yet")):
        aocd.get_data(year=2101, day=1)
    assert mock.calls == 1


def test_puzzle_not_available_yet_block(pook, caplog, mocker):
    mock = pook.get(
        url="https://adventofcode.com/2101/day/1/input",
        response_body="Not Found",
        reply=404,
        times=2,
    )
    blocker = mocker.patch("aocd.get.blocker")
    with pytest.raises(PuzzleLockedError("2101/01 not available yet")):
        aocd.get_data(year=2101, day=1, block="q")
    assert mock.calls == 2
    blocker.assert_called_once_with(quiet=True, until=(2101, 1))


def test_req_headers(pook):
    v = version("advent-of-code-data")
    expected = f"github.com/wimglenn/advent-of-code-data v{v} by hey@wimglenn.com"
    mock = pook.get(
        url="https://adventofcode.com/2018/day/1/input",
        headers={
            "Cookie": "session=thetesttoken",
            "User-Agent": expected,
        },
    )
    aocd.get_data(year=2018, day=1)
    assert mock.calls == 1


def test_data_is_cached_from_successful_request(aocd_data_dir, pook):
    pook.get(
        url="https://adventofcode.com/2018/day/1/input",
        response_body="fake data for year 2018 day 1",
    )
    cached = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    assert not cached.exists()
    aocd.get_data(year=2018, day=1)
    assert cached.exists()
    assert cached.read_text() == "fake data for year 2018 day 1"


def test_corrupted_cache(aocd_data_dir):
    cached = aocd_data_dir / "testauth.testuser.000" / "2018_01_input.txt"
    cached.mkdir(parents=True)
    with pytest.raises(OSError):
        aocd.get_data(year=2018, day=1)


def test_race_on_download_data(mocker, aocd_data_dir, pook):
    pook.get(
        url="https://adventofcode.com/2018/day/1/input",
        response_body="fake data for year 2018 day 1",
        times=2,
    )
    open_evt = threading.Event()
    write_evt = threading.Event()

    real_os_open = os.open
    fds = {}

    def logging_os_open(path, *args, **kwargs):
        ret = real_os_open(path, *args, **kwargs)
        fds[ret] = path
        return ret

    mocker.patch("os.open", side_effect=logging_os_open)

    # This doesn't use unittest.mock_open because we actually do want the faked object to be functional.
    # We don't want fake results or to assert things are called in a certain order; we just want the
    # write operation to be slow.
    def generate_open(real_open):
        def open_impl(file, *args, **kwargs):
            res = real_open(file, *args, **kwargs)
            filename = fds[file] if isinstance(file, int) else file
            if "aocd-data" not in str(filename):
                return res
            open_evt.set()
            real_write = res.write

            def write(*args, **kwargs):
                write_evt.wait()
                real_write(*args, **kwargs)

            res.write = write
            return res

        return open_impl

    mocker.patch("io.open", side_effect=generate_open(io.open))

    t = threading.Thread(target=aocd.get_data, kwargs={"year": 2018, "day": 1})
    t.start()
    open_evt.wait()
    mocker.stopall()
    data = aocd.get_data(year=2018, day=1)
    write_evt.set()
    assert data == "fake data for year 2018 day 1"
