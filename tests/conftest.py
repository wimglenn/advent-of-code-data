from __future__ import unicode_literals

import pytest

from aocd.models import User


@pytest.fixture(autouse=True)
def mocked_sleep(mocker):
    no_sleep_till_brooklyn = mocker.patch("time.sleep")
    return no_sleep_till_brooklyn


@pytest.fixture
def aocd_data_dir(tmp_path):
    data_dir = tmp_path / ".config" / "aocd-data"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def aocd_config_dir(tmp_path):
    token_dir = tmp_path / ".config" / "aocd-config"
    token_dir.mkdir(parents=True)
    return token_dir


@pytest.fixture(autouse=True)
def remove_user_env(aocd_data_dir, monkeypatch, aocd_config_dir):
    monkeypatch.setattr("aocd.runner.AOCD_CONFIG_DIR", str(aocd_config_dir))
    monkeypatch.setattr("aocd.models.AOCD_DATA_DIR", str(aocd_data_dir))
    monkeypatch.setattr("aocd.models.AOCD_CONFIG_DIR", str(aocd_config_dir))
    monkeypatch.setattr("aocd.cookies.AOCD_CONFIG_DIR", str(aocd_config_dir))
    monkeypatch.delenv(str("AOC_SESSION"), raising=False)


@pytest.fixture(autouse=True)
def test_token(aocd_config_dir, aocd_data_dir):
    token_file = aocd_config_dir / "token"
    cache_dir = aocd_data_dir / "testauth.testuser.000"
    cache_dir.mkdir()
    token_file.write_text("thetesttoken")
    return token_file


@pytest.fixture(autouse=True)
def answer_not_cached(request, mocker):
    install = True
    rv = None

    mark = request.node.get_closest_marker("answer_not_cached")
    if mark:
        install = mark.kwargs.get("install", True)
        rv = mark.kwargs.get("rv", None)

    if install:
        mocker.patch("aocd.models.Puzzle._check_guess_against_existing", return_value=rv)


@pytest.fixture(autouse=True)
def detect_user_id(requests_mock):
    requests_mock.get(
        "https://adventofcode.com/settings",
        text="<span>Link to testauth/testuser</span><code>000</code>",
    )
    yield
    if getattr(User, "_token2id", None) is not None:
        User._token2id = None
