import argparse
import logging
import os
import sys

import bs4
import requests


log = logging.getLogger(__name__)


def scrape_session_tokens():
    parser = argparse.ArgumentParser(description="Scrapes AoC session tokens from your browser's cookie storage")
    parser.add_argument("-v", "--verbose", action="count", help="increased logging (may be specified multiple)")
    args = parser.parse_args()
    if args.verbose is None:
        log_level = logging.WARNING
    elif args.verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)

    log.debug("checking for installation of browser-cookie3 package")
    try:
        import browser_cookie3 as bc3  # soft dependency
    except ImportError:
        sys.exit("To use this feature you must install browser-cookie3")

    log.info("checking browser cookies storage for auth tokens, this might pop up an auth dialog!")
    log.info("checking chrome cookie jar...")
    cookie_jar_chrome = bc3.chrome(domain_name=".adventofcode.com")
    chrome = [c for c in cookie_jar_chrome if c.name == "session"]
    log.info("%d candidates from chrome", len(chrome))

    log.info("checking firefox cookie jar...")
    cookie_jar_firefox = bc3.firefox(domain_name=".adventofcode.com")
    firefox = [c for c in cookie_jar_firefox if c.name == "session"]
    log.info("%d candidates from firefox", len(firefox))

    url = "https://adventofcode.com/settings"

    working = {}  # map of {token: auth source}
    for cookie in chrome + firefox:
        token = cookie.value
        response = requests.get(url, cookies={"session": token}, allow_redirects=False)
        if response.status_code != 200:
            # bad tokens will 302 redirect to main page
            log.info("session %s is dead - status_code=%s", token, response.status_code)
            continue
        working[token] = "unknown/unknown"
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        for span in soup.find_all("span"):
            if span.text.startswith("Link to "):
                auth_source = span.text[8:]
                auth_source = auth_source.replace("https://twitter.com/", "twitter/")
                auth_source = auth_source.replace("https://github.com/", "github/")
                auth_source = auth_source.replace("https://www.reddit.com/u/", "reddit/")
                log.debug("found %r", span.text)
                working[token] = auth_source
            elif span.img is not None:
                if "googleusercontent.com" in span.img.attrs.get("src", ""):
                    log.debug("found google user content img, getting google username")
                    working[token] = "google/" + span.text

    if not working:
        sys.exit("could not find any working tokens in browser cookies, sorry :(")

    log.debug("found %d live tokens", len(working))
    for cookie in working.items():
        print("%s <- %s" % cookie)

    aocd_dir = os.path.expanduser(os.environ.get("AOCD_DIR", "~/.config/aocd"))
    aocd_token_file = os.path.join(aocd_dir, "token")
    if "AOC_SESSION" not in os.environ:
        if not os.path.isfile(aocd_token_file):
            if len(working) == 1:
                [(token, auth_source)] = working.items()
                with open(aocd_token_file, "w") as f:
                    f.write(token)
                    log.info("wrote %s session to %s", auth_source, aocd_token_file)
