from __future__ import unicode_literals

import pytest


@pytest.fixture(autouse=True)
def mocked_sleep(mocker):
    no_sleep_till_brooklyn = mocker.patch("time.sleep")
    return no_sleep_till_brooklyn


@pytest.fixture
def aocd_dir(tmp_path):
    data_dir = tmp_path / ".config" / "aocd"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture(autouse=True)
def remove_user_env(aocd_dir, monkeypatch):
    monkeypatch.setattr("aocd.runner.AOCD_DIR", str(aocd_dir))
    monkeypatch.setattr("aocd.models.AOCD_DIR", str(aocd_dir))
    monkeypatch.delenv("AOC_SESSION", raising=False)


@pytest.fixture(autouse=True)
def test_token(aocd_dir):
    token_file = aocd_dir / "token"
    token_dir = aocd_dir / "thetesttoken"
    token_dir.mkdir()
    token_file.write_text("thetesttoken")
    return token_file
