import pytest


@pytest.fixture(autouse=True)
def mocked_sleep(mocker):
    no_sleep_till_brooklyn = mocker.patch("time.sleep")
    return no_sleep_till_brooklyn


@pytest.fixture(autouse=True)
def remove_user_env(tmpdir, monkeypatch):
    memo_dir = tmpdir / ".config/aocd"
    monkeypatch.setattr("aocd.runner.AOCD_DIR", str(memo_dir))
    monkeypatch.setattr("aocd.models.AOCD_DIR", str(memo_dir))
    monkeypatch.delenv("AOC_SESSION", raising=False)


@pytest.fixture
def aocd_dir(tmpdir):
    data_dir = tmpdir / ".config/aocd"
    data_dir.ensure_dir()
    return data_dir


@pytest.fixture(autouse=True)
def test_token(aocd_dir):
    token_file = aocd_dir / "token"
    token_file.ensure(file=True)
    token_file.write("thetesttoken")
    return token_file
