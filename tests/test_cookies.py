import pytest

from aocd.cookies import scrape_session_tokens


def test_cookie_scrape(mocker, capsys):
    mocker.patch("sys.argv", ["aocd-token", "--check"])
    with pytest.raises(SystemExit(0)):
        scrape_session_tokens()
    out, err = capsys.readouterr()
    assert out.startswith("thetesttoken")
    assert out.strip().endswith("is alive")

def test_check_with_corrupt_tokens_json(mocker, aocd_config_dir):
    (aocd_config_dir / "tokens.json").write_text("{not valid json", encoding="utf-8")
    mocker.patch("sys.argv", ["aocd-token", "--check"])
    with pytest.raises(SystemExit) as exc_info:
        scrape_session_tokens()
    assert "is not valid JSON" in str(exc_info.value.code)
