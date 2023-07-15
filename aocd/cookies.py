import argparse
import glob
import json
import logging
import os
import sys

from .exceptions import DeadTokenError
from .models import AOCD_CONFIG_DIR
from .utils import _ensure_intermediate_dirs
from .utils import colored
from .utils import get_owner


log = logging.getLogger(__name__)


def get_working_tokens():
    """Check browser cookie storage for session tokens from .adventofcode.com domain."""
    log.debug("checking for installation of browser-cookie3 package")
    try:
        import browser_cookie3 as bc3  # soft dependency
    except ImportError:
        sys.exit("To use this feature you must pip install browser-cookie3")

    log.info("checking browser storage for tokens, this might pop up an auth dialog!")
    log.info("checking chrome cookie jar...")
    cookie_files = glob.glob(os.path.expanduser("~/.config/google-chrome/*/Cookies"))
    cookie_files.append(None)
    chrome_cookies = []
    for cf in cookie_files:
        try:
            chrome = bc3.chrome(cookie_file=cf, domain_name=".adventofcode.com")
        except Exception as err:
            log.debug("Couldn't scrape chrome - %s: %s", type(err), err)
        else:
            chrome_cookies += [c for c in chrome if c.name == "session"]
    log.info("%d candidates from chrome", len(chrome_cookies))
    chrome = chrome_cookies

    log.info("checking firefox cookie jar...")
    try:
        firefox = bc3.firefox(domain_name=".adventofcode.com")
    except Exception as err:
        log.debug("Couldn't scrape firefox - %s: %s", type(err), err)
        firefox = []
    else:
        firefox = [c for c in firefox if c.name == "session"]
        log.info("%d candidates from firefox", len(firefox))

    # order preserving de-dupe
    tokens = list({}.fromkeys([c.value for c in chrome + firefox]))
    removed = len(chrome + firefox) - len(tokens)
    if removed:
        log.info("Removed %d duplicate%s", removed, "s"[: removed - 1])

    result = {}  # map of {token: auth source}
    for token in tokens:
        try:
            owner = get_owner(token)
        except DeadTokenError:
            pass
        else:
            result[token] = owner

    return result


def scrape_session_tokens():
    """Scrape AoC session tokens from your browser's cookie storage."""
    aocd_token_path = AOCD_CONFIG_DIR / "token"
    aocd_tokens_path = AOCD_CONFIG_DIR / "tokens.json"

    parser = argparse.ArgumentParser(description=scrape_session_tokens.__doc__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="increased logging (may be specified multiple)",
    )
    parser.add_argument(
        "-c",
        "--check",
        nargs="?",
        help="check existing token(s) and exit",
        const=True,
    )
    args = parser.parse_args()

    if args.verbose is None:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)
    log.debug("called with %r", args)

    if args.check is not None:
        if args.check is True:
            tokens = {}
            if os.environ.get("AOC_SESSION"):
                tokens["AOC_SESSION"] = os.environ["AOC_SESSION"]
            if aocd_token_path.is_file():
                txt = aocd_token_path.read_text(encoding="utf-8").strip()
                if txt:
                    tokens[aocd_token_path] = txt.split()[0]
            if aocd_tokens_path.is_file():
                tokens.update(json.loads(aocd_tokens_path.read_text(encoding="utf-8")))
        else:
            tokens = {"CLI": args.check}
        if not tokens:
            sys.exit("no existing tokens found")
        log.debug("%d tokens to check", len(tokens))
        for name, token in tokens.items():
            try:
                owner = get_owner(token)
            except DeadTokenError:
                print(colored(f"{token} ({name}) is dead", color="red"))
            else:
                print(f"{token} ({name}) is alive")
                if name != owner:
                    log.info(f"{token} ({name}) is owned by {owner}")
        sys.exit(0)

    working = get_working_tokens()
    if not working:
        sys.exit("could not find any working tokens in browser cookies, sorry :(")

    log.debug("found %d live tokens", len(working))
    for token, auth_source in working.items():
        print(f"{token} <- {auth_source}")

    if "AOC_SESSION" not in os.environ:
        if not aocd_token_path.is_file():
            if len(working) == 1:
                [(token, auth_source)] = working.items()
                _ensure_intermediate_dirs(aocd_token_path)
                aocd_token_path.write_text(token, encoding="utf-8")
                log.info("wrote %s session to %s", auth_source, aocd_token_path)
