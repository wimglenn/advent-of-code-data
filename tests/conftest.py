import pytest


@pytest.fixture(autouse=True)
def mocked_sleep(mocker):
    no_sleep_till_brooklyn = mocker.patch("aocd._module.time.sleep")
    return no_sleep_till_brooklyn


@pytest.fixture(autouse=True)
def remove_user_env(tmpdir, monkeypatch):
    token_file = tmpdir / ".config/aocd/token"
    memo = tmpdir / ".config/aocd/{session}/{year}/{day}.txt"
    monkeypatch.setattr("aocd._module.CONF_FNAME", str(token_file))
    monkeypatch.setattr("aocd._module.MEMO_FNAME", str(memo))
    monkeypatch.delenv("AOC_SESSION", raising=False)


@pytest.fixture(autouse=True)
def test_token(tmpdir):
    token_file = tmpdir / ".config/aocd/token"
    token_file.ensure(file=True)
    token_file.write("thetesttoken")
    return token_file
