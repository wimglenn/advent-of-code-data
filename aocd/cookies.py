import argparse
import glob
import json
import logging
import os
import sys

from aocd.exceptions import DeadTokenError
from aocd.models import AOCD_DIR
from aocd.utils import _ensure_intermediate_dirs
from aocd.utils import get_owner


log = logging.getLogger(__name__)


def scrape_session_tokens():
    aocd_token_file = os.path.join(AOCD_DIR, "token")
    aocd_tokens_file = os.path.join(AOCD_DIR, "tokens.json")

    parser = argparse.ArgumentParser(description="Scrapes AoC session tokens from your browser's cookie storage")
    parser.add_argument("-v", "--verbose", action="count", help="increased logging (may be specified multiple)")
    parser.add_argument("-c", "--check", nargs="?", help="check existing token(s) and exit", const=True)
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
            if os.path.isfile(aocd_token_file):
                with open(aocd_token_file) as f:
                    txt = f.read().strip()
                    if txt:
                        tokens[aocd_token_file] = txt.split()[0]
            if os.path.isfile(aocd_tokens_file):
                with open(aocd_tokens_file) as f:
                    tokens.update(json.load(f))
        else:
            tokens = {"CLI": args.check}
        if not tokens:
            sys.exit("no existing tokens found")
        log.debug("%d tokens to check", len(tokens))
        for name, token in tokens.items():
            try:
                owner = get_owner(token)
            except DeadTokenError:
                print("{} ({}) is dead".format(token, name))
            else:
                print("{} ({}) is alive".format(token, name))
                if name != owner:
                    log.info("{} ({}) is owned by {}".format(token, name, owner))
        sys.exit(0)

    log.debug("checking for installation of browser-cookie3 package")
    try:
        import browser_cookie3 as bc3  # soft dependency
    except ImportError:
        sys.exit("To use this feature you must pip install browser-cookie3")

    log.info("checking browser cookies storage for auth tokens, this might pop up an auth dialog!")
    log.info("checking chrome cookie jar...")
    cookie_files = glob.glob(os.path.expanduser("~/.config/google-chrome/*/Cookies")) + [None]
    chrome_cookies = []
    for cookie_file in cookie_files:
        try:
            chrome = bc3.chrome(cookie_file=cookie_file, domain_name=".adventofcode.com")
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
        log.info("Removed %d duplicate%s", removed, "s"[:removed-1])

    working = {}  # map of {token: auth source}
    for token in tokens:
        try:
            owner = get_owner(token)
        except DeadTokenError:
            pass
        else:
            working[token] = owner

    if not working:
        sys.exit("could not find any working tokens in browser cookies, sorry :(")

    log.debug("found %d live tokens", len(working))
    for cookie in working.items():
        print("%s <- %s" % cookie)

    if "AOC_SESSION" not in os.environ:
        if not os.path.isfile(aocd_token_file):
            if len(working) == 1:
                [(token, auth_source)] = working.items()
                _ensure_intermediate_dirs(aocd_token_file)
                with open(aocd_token_file, "w") as f:
                    f.write(token)
                    log.info("wrote %s session to %s", auth_source, aocd_token_file)
