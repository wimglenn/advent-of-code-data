import pytest

from aocd.cookies import scrape_session_tokens


def test_cookie_scrape(mocker, capsys):
    mocker.patch("sys.argv", ["aocd-token", "--check"])
    with pytest.raises(SystemExit(0)):
        scrape_session_tokens()
    out, err = capsys.readouterr()
    assert out.startswith("thetesttoken")
    assert out.strip().endswith("is alive")
