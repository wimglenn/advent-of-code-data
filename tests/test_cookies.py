import pytest
from pytest_mock import MockerFixture

from aocd.cookies import scrape_session_tokens


def test_cookie_scrape(mocker: MockerFixture, capsys):
    mocker.patch("sys.argv", ["aocd-token", "--check"])
    with pytest.raises(SystemExit(0)):
        scrape_session_tokens()
    out, err = capsys.readouterr()
    assert out.startswith("thetesttoken")
    assert out.strip().endswith("is alive")
