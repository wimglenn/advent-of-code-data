import pytest


@pytest.fixture(autouse=True)
def mocked_sleep(mocker):
    no_sleep_till_brooklyn = mocker.patch("time.sleep")
    return no_sleep_till_brooklyn


@pytest.fixture(autouse=True)
def remove_user_env(tmpdir, monkeypatch):
    memo_dir = tmpdir / ".config/aocd"
    monkeypatch.setattr("aocd.models.CONF_DIR", str(memo_dir))
    monkeypatch.delenv("AOC_SESSION", raising=False)


@pytest.fixture(autouse=True)
def test_token(tmpdir):
    token_file = tmpdir / ".config/aocd/token"
    token_file.ensure(file=True)
    token_file.write("thetesttoken")
    return token_file
