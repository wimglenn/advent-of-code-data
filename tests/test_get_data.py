import io
import logging
import os
import sys
import threading

import pytest

import aocd
from aocd.exceptions import AocdError
from aocd.exceptions import PuzzleLockedError


def test_get_from_server(requests_mock):
    mock = requests_mock.get(
        url="https://adventofcode.com/2018/day/1/input",
        text="fake data for year 2018 day 1",
    )
    data = aocd.get_data(year=2018, day=1)
    assert data == "fake data for year 2018 day 1"
    assert mock.called
    assert mock.call_count == 1


def test_get_data_uses_current_date_if_unspecified(requests_mock, freezer):
    mock = requests_mock.get(
        url="https://adventofcode.com/2017/day/17/input",
        text="fake data for year 2017 day 17",
    )
    freezer.move_to("2017-12-17 12:00:00Z")
    data = aocd.get_data()
    assert data == "fake data for year 2017 day 17"
    assert mock.called
    assert mock.call_count == 1


def test_saved_data_is_reused_if_available(aocd_data_dir, requests_mock):
    mock = requests_mock.get(
        url="https://adventofcode.com/2018/day/1/input",
        text="fake data for year 2018 day 1",
    )
    cached = aocd_data_dir / "testauth.testuser.000/2018_01_input.txt"
    cached.touch()
    cached.write_text(u"saved data for year 2018 day 1")
    data = aocd.get_data(year=2018, day=1)
    assert data == "saved data for year 2018 day 1"
    assert not mock.called


def test_server_error(requests_mock, caplog):
    mock = requests_mock.get(
        url="https://adventofcode.com/2101/day/1/input",
        text="AWS meltdown",
        status_code=500,
    )
    with pytest.raises(AocdError) as exc_info:
        aocd.get_data(year=2101, day=1)
    assert "Unexpected response" == str(exc_info.value)
    assert mock.called
    assert mock.call_count == 1
    assert caplog.record_tuples == [
        ("aocd.models", logging.ERROR, "got 500 status code token=...oken"),
        ("aocd.models", logging.ERROR, "AWS meltdown"),
    ]


def test_puzzle_not_available_yet(requests_mock, caplog):
    mock = requests_mock.get(
        url="https://adventofcode.com/2101/day/1/input",
        text="Not Found",
        status_code=404,
    )
    with pytest.raises(PuzzleLockedError) as exc_info:
        aocd.get_data(year=2101, day=1)
    assert "2101/01 not available yet" == str(exc_info.value)
    assert mock.called
    assert mock.call_count == 1


def test_puzzle_not_available_yet_block(requests_mock, caplog, mocker):
    mock = requests_mock.get(
        url="https://adventofcode.com/2101/day/1/input",
        text="Not Found",
        status_code=404,
    )
    blocker = mocker.patch("aocd._module.get.blocker")
    with pytest.raises(PuzzleLockedError) as exc_info:
        aocd.get_data(year=2101, day=1, block="q")
    assert "2101/01 not available yet" == str(exc_info.value)
    assert mock.called
    assert mock.call_count == 2
    blocker.assert_called_once_with(quiet=True, until=(2101, 1))


def test_session_token_in_req_headers(requests_mock):
    mock = requests_mock.get("https://adventofcode.com/2018/day/1/input")
    aocd.get_data(year=2018, day=1)
    assert mock.call_count == 1
    headers = mock.last_request._request.headers
    assert headers["Cookie"] == "session=thetesttoken"


def test_aocd_user_agent_in_req_headers(requests_mock):
    mock = requests_mock.get("https://adventofcode.com/2018/day/1/input")
    aocd.get_data(year=2018, day=1)
    assert mock.call_count == 1
    headers = mock.last_request._request.headers
    expected = "github.com/wimglenn/advent-of-code-data v{} by hey@wimglenn.com".format(aocd.__version__)
    assert headers["User-Agent"] == expected


def test_data_is_cached_from_successful_request(aocd_data_dir, requests_mock):
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1/input",
        text="fake data for year 2018 day 1",
    )
    cached = aocd_data_dir / "testauth.testuser.000/2018_01_input.txt"
    assert not cached.exists()
    aocd.get_data(year=2018, day=1)
    assert cached.exists()
    assert cached.read_text() == "fake data for year 2018 day 1"


def test_corrupted_cache(aocd_data_dir):
    cached = aocd_data_dir / "testauth.testuser.000/2018_01_input.txt"
    cached.mkdir(parents=True)
    with pytest.raises(IOError):
        aocd.get_data(year=2018, day=1)


def test_race_on_download_data(mocker, aocd_data_dir, requests_mock):
    requests_mock.get(
        url="https://adventofcode.com/2018/day/1/input",
        text="fake data for year 2018 day 1",
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
            if "aocd-data" not in filename:
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
    PY2 = sys.version_info.major < 3
    mocker.patch("__builtin__.open" if PY2 else "builtins.open", side_effect=generate_open(open))

    t = threading.Thread(target=aocd.get_data, kwargs={"year": 2018, "day": 1})
    t.start()
    # This doesn't quite work on python 2 because the io.open patch doesn't seem to work.
    # We still get coverage by making sure the right thing happens in py3, though.
    if not PY2:
        open_evt.wait()
    mocker.stopall()
    data = aocd.get_data(year=2018, day=1)
    write_evt.set()
    assert data == "fake data for year 2018 day 1"
