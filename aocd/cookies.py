import argparse
import glob
import json
import logging
import os
import sys

import bs4
import requests

from aocd.models import AOCD_DIR
from aocd.utils import _ensure_intermediate_dirs


log = logging.getLogger(__name__)


def get_owner(token):
    """parse owner of the token. returns None if the token is expired/invalid"""
    url = "https://adventofcode.com/settings"
    response = requests.get(url, cookies={"session": token}, allow_redirects=False)
    if response.status_code != 200:
        # bad tokens will 302 redirect to main page
        log.info("session %s is dead - status_code=%s", token, response.status_code)
        return
    result = "unknown/unknown"
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    for span in soup.find_all("span"):
        if span.text.startswith("Link to "):
            auth_source = span.text[8:]
            auth_source = auth_source.replace("https://twitter.com/", "twitter/")
            auth_source = auth_source.replace("https://github.com/", "github/")
            auth_source = auth_source.replace("https://www.reddit.com/u/", "reddit/")
            log.debug("found %r", span.text)
            result = auth_source
        elif span.img is not None:
            if "googleusercontent.com" in span.img.attrs.get("src", ""):
                log.debug("found google user content img, getting google username")
                result = "google/" + span.text
    return result


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
            owner = get_owner(token)
            if owner is None:
                print("{} ({}) is dead".format(token, name))
            else:
                print("{} ({}) is live - {}".format(token, name, owner))
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
        owner = get_owner(token)
        if owner is not None:
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
