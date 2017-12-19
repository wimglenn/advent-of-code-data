from __future__ import print_function

import atexit
import errno
import json
import os
import re
import sys
import time
import traceback
import webbrowser
from datetime import datetime
from functools import partial

import bs4
import pytz
import requests
from termcolor import cprint


__version__ = '0.4.2'


URI = 'http://adventofcode.com/{year}/day/{day}/'
AOC_TZ = pytz.timezone('America/New_York')
CONF_FNAME = os.path.expanduser('~/.aocdrc')
MEMO_FNAME = os.path.expanduser('~/.aocd_memo.json')
RATE_LIMIT = 10  # seconds between consecutive requests
USER_AGENT = 'aocd.py/v{}'.format(__version__)


class AocdError(Exception):
    pass


memo = {}
try:
    with open(MEMO_FNAME) as f:
        memo = json.load(f)
except (OSError, IOError) as err:
    if err.errno != errno.ENOENT:
        raise AocdError('Problem loading memo')


def dump_memo():
    with open(MEMO_FNAME, 'w') as f:
        json.dump(memo, f, sort_keys=True, indent=2)


def eprint(*args, **kwargs):
    cprint(*args, color='red', file=sys.stderr, **kwargs)


def get_data(session=None, day=None, year=None):
    """
    Get data for day (1-25) and year (> 2015)
    User's session cookie is needed (puzzle inputs differ by user)
    """
    if session is None:
        session = get_cookie()
    if day is None:
        day = guess_day()
    if year is None:
        year = guess_year()
    uri = URI.format(year=year, day=day) + 'input'
    key = '{}?session={}'.format(uri, session)
    if key not in memo:
        try:
            delta = (datetime.now() - get_data.last_request).total_seconds()
        except AttributeError:
            # it's the first request
            pass
        else:
            t_sleep = max(RATE_LIMIT - delta, 0)
            if t_sleep > 0:
                cprint('You are being rate-limited.', color='red')
                cprint('Sleeping {} seconds...'.format(t_sleep))
                time.sleep(t_sleep)
                cprint('Done.')
        response = requests.get(uri, 
            cookies={'session': session}, headers={'User-Agent': USER_AGENT},
        )
        get_data.last_request = datetime.now()
        if response.status_code != 200:
            eprint(response.status_code)
            eprint(response.content)
            raise AocdError('Unexpected response')
        memo[key] = response.text
        if not getattr(dump_memo, 'registered', False):
            atexit.register(dump_memo)
            dump_memo.registered = True
    return memo[key].rstrip('\r\n')


def guess_year():
    """
    This year, if it's December.  
    The most recent year, otherwise.
    Note: Advent of Code started in 2015
    """
    aoc_now = datetime.now(tz=AOC_TZ)
    year = aoc_now.year
    if aoc_now.month < 12:
        year -= 1
    if year < 2015:
        raise AocdError('Time travel not supported yet')
    return year


def guess_day():
    """
    Most recent day, if it's during the Advent of Code.  Happy Holidays!
    Raises exception otherwise.
    """
    aoc_now = datetime.now(tz=AOC_TZ)
    if aoc_now.month != 12:
        raise AocdError('guess_day is only available in December (EST)')
    day = min(aoc_now.day, 25)
    return day


def get_cookie():
    # export your session id as AOC_SESSION env var
    cookie = os.getenv('AOC_SESSION')
    if cookie:
        return cookie

    # or chuck it in a file at ~/.aocdrc
    try:
        with open(CONF_FNAME) as f:
            cookie = f.read().strip()
    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise AocdError('Wat')
    if cookie:
        return cookie

    # heck, you can just paste it in directly here if you want:
    cookie = ''
    if cookie:
        return cookie

    eprint('ERROR: AoC session ID is needed to get your puzzle data!')
    eprint('You can find it in your browser cookies after login.')
    eprint('    1) Save the cookie into a text file {}, or'.format(CONF_FNAME))
    eprint('    2) Export the cookie in environment variable AOC_SESSION')

    raise AocdError('Missing session ID')


def skip_frame(name):
    basename = os.path.basename(name)
    skip = any([
        name == __file__,
        'importlib' in name,  # Python 3 import machinery
        '/IPython/' in name,  # ipython adds a tonne of stack frames
        name.startswith('<'),  # crap like <decorator-gen-57>
        name.endswith('ython3'),  # ipython3 alias
        not re.search(r'[1-9]', basename),  # no digits in filename
    ])
    return skip


def introspect_date():
    """
    Here be dragons.  This is some black magic so that lazy users can get 
    their puzzle input simply by using `from aocd import data`.  The day is
    parsed from the filename which used the import statement.  

    This means your filenames should be something simple like "q03.py" or 
    "xmas_problem_2016_25b_dawg.py".  A filename like "problem_one.py" will 
    break shit, so don't do that.  If you don't like weird frame hacks, just 
    use the aocd.get_data() function and have a nice day!
    """
    pattern_year = r'201[5-9]'
    pattern_day = r'2[0-5]|1[0-9]|[1-9]'
    stack = [f[0] for f in traceback.extract_stack()]
    for name in stack:
        if not skip_frame(name):
            abspath = os.path.abspath(name)
            break
    else:
        raise AocdError('Failed introspection of filename')
    years = {int(year) for year in re.findall(pattern_year, abspath)}
    if len(years) > 1:
        raise AocdError('Failed introspection of year')
    year = years.pop() if years else None
    fname = re.sub(pattern_year, '', abspath)
    try:
        n = re.findall(pattern_day, fname)[-1]
    except ValueError:
        pass
    else:
        assert not n.startswith('0')  # regex must prevent any leading 0
        n = int(n)
        if 1 <= n <= 25:
            return n, year
    raise AocdError('Failed introspection of day')


def is_interactive():
    import __main__
    try:
        __main__.__file__
    except AttributeError:
        return True
    else:
        return False


def submit(answer, level, day=None, year=None, session=None, reopen=True):
    if level not in {1, 2, '1', '2'}:
        raise AocdError('level must be 1 or 2')
    if session is None:
        session = get_cookie()
    if day is None:
        day = guess_day()
    if year is None:
        year = guess_year()
    uri = URI.format(year=year, day=day) + 'answer'
    response = requests.post(
        uri,
        cookies={'session': session},
        headers={'User-Agent': USER_AGENT},
        data={'level': level, 'answer': answer},
    )
    if not response.ok:
        raise AocdError('Non-200 response for POST: {}'.format(response))
    soup = bs4.BeautifulSoup(response.text, 'lxml')
    message = soup.article.text
    if "That's the right answer" in message:
        color = 'green'
        if reopen:
            webbrowser.open(response.url)  # So you can read part B on the website...
    elif "Did you already complete it" in message:
        color = 'yellow'
    elif "That's not the right answer" in message or "You gave an answer too recently" in message:
        color = 'red'
    else:
        color = None
    cprint(soup.article.text, color=color)
    return response


def submit1(answer, year=None, day=None, session=None, reopen=True):
    return submit(answer, level=1, day=day, year=year, session=session, reopen=reopen)


def submit2(answer, year=None, day=None, session=None, reopen=True):
    return submit(answer, level=2, day=day, year=year, session=session, reopen=reopen)


if is_interactive():
    try:
        data = get_data()
    except AocdError:
        data = None
else:
    try:
        day, year = introspect_date()
        data = get_data(day=day, year=year)
        submit = partial(submit, day=day, year=year)
        submit1 = partial(submit1, day=day, year=year)
        submit2 = partial(submit2, day=day, year=year)
    except AocdError:
        data = None
