Advent of Code data
===================

|pyversions|_ |pypi|_ |womm|_ |actions|_ |codecov|_

.. |pyversions| image:: https://img.shields.io/pypi/pyversions/advent-of-code-data.svg
.. _pyversions: 

.. |pypi| image:: https://img.shields.io/pypi/v/advent-of-code-data.svg
.. _pypi: https://pypi.org/project/advent-of-code-data/

.. |womm| image:: https://cdn.rawgit.com/nikku/works-on-my-machine/v0.2.0/badge.svg
.. _womm: https://github.com/nikku/works-on-my-machine

.. |actions| image:: https://github.com/wimglenn/advent-of-code-data/actions/workflows/tests.yml/badge.svg
.. _actions: https://github.com/wimglenn/advent-of-code-data/actions/workflows/tests.yml

.. |codecov| image:: https://codecov.io/gh/wimglenn/advent-of-code-data/branch/master/graph/badge.svg
.. _codecov: https://codecov.io/gh/wimglenn/advent-of-code-data


Get your puzzle data with a single import statement:

.. code-block:: python

   from aocd import data

Might be useful for lazy Pythonistas and speedhackers.

If you'd just like to print or keep your own input files, there's a shell entry point for that:

.. code-block:: bash

   aocd > input.txt  # saves today's data
   aocd 13 2018 > day13.txt  # save some other day's data

There are currently two convenience transforms (maybe more to come later):

.. code-block:: python

   from aocd import lines  # like data.splitlines()
   from aocd import numbers  # uses regex pattern -?\d+ to extract integers from data

If all that sounds too magical, there is a simple getter function to just return your raw data.

.. code-block:: python

   >>> from aocd import get_data
   >>> get_data(day=24, year=2015)
   '1\n2\n3\n7\n11\n13\n17\n19\n23\n31...

Note that ``aocd`` will cache puzzle inputs and answers (including incorrect guesses) clientside, to save unnecessary requests to the server.


Quickstart
----------

Install with pip

.. code-block:: bash

   pip install advent-of-code-data

**Puzzle inputs differ by user.**   So export your session ID, for example:

.. code-block:: bash

   export AOC_SESSION=cafef00db01dfaceba5eba11deadbeef

This is a cookie which is set when you login to AoC.  You can find it with
your browser inspector.  If you're hacking on AoC at all you probably already
know these kind of tricks, but if you need help with that part then you can
`look here <https://github.com/wimglenn/advent-of-code/issues/1>`_.

*Note:* If you don't like the env var, you could also keep your token(s) in files.
By default the location is ``~/.config/aocd/token``. Set the ``AOCD_DIR`` environment
variable to some existing directory if you wish to use another location to store token(s).

*New in version 0.9.0.* There's a utility script ``aocd-token`` which attempts to
find session tokens from your browser's cookie storage. This feature is experimental
and requires you to additionally install the package ``browser-cookie3``. Only Chrome
and Firefox browsers are currently supported. On macOS, you may get an authentication
dialog requesting permission, since Python is attempting to read browser storage files.
This is expected, the script *is* actually scraping those private files to access AoC
session token(s).

If this utility script was able to locate your token, you can save it to file with:

.. code-block:: bash

   $ aocd-token > ~/.config/aocd/token

Automated submission
--------------------

*New in version 0.4.0.* Basic use:

.. code-block:: python

   from aocd import submit
   submit(my_answer, part="a", day=25, year=2017)

Note that the same filename introspection of year/day also works for automated
submission. There's also introspection of the "level", i.e. part a or part b,
aocd can automatically determine if you have already completed part a or not
and submit your answer for the correct part accordingly. In this case, just use:

.. code-block:: python

   from aocd import submit
   submit(my_answer)

The response message from AoC will be printed in the terminal. If you gave
the right answer, then the puzzle will be refreshed in your web browser
(so you can read the instructions for the next part, for example).
**Proceed with caution!** If you submit wrong guesses, your user **WILL**
get rate-limited by Eric, so don't call submit until you're fairly confident
you have a correct answer!


OOP-style interfaces
--------------------

*New in version 0.8.0.*

Input data is via regular attribute access. Example usage:

.. code-block:: python

    >>> from aocd.models import Puzzle
    >>> puzzle = Puzzle(year=2017, day=20)
    >>> puzzle
    <Puzzle(2017, 20) at 0x107322978 - Particle Swarm>
    >>> puzzle.input_data
    'p=<-1027,-979,-188>, v=<7,60,66>, a=<9,1,-7>\np=<-1846,-1539,-1147>, v=<88,145,67>, a=<6,-5,2> ...

Submitting answers is also by regular attribute access. Any incorrect answers you submitted are remembered, and aocd will prevent you from attempting to submit the same incorrect value twice:

.. code-block:: python

    >>> puzzle.answer_a = 299
    That's not the right answer; your answer is too high. If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit. Please wait one minute before trying again. (You guessed 299.) [Return to Day 20]
    >>> puzzle.answer_a = 299
    aocd will not submit that answer again. You've previously guessed 299 and the server responded:
    That's not the right answer; your answer is too high. If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit. Please wait one minute before trying again. (You guessed 299.) [Return to Day 20]

Your own solutions can be executed by writing and using an `entry-point <https://packaging.python.org/specifications/entry-points/>`_ into your code, registered in the group ``"adventofcode.user"``. Your entry-point should resolve to a callable, and it will be called with three keyword arguments: ``year``, ``day``, and ``data``. For example, `my entry-point is called "wim" <https://github.com/wimglenn/advent-of-code-wim/blob/d033366c16fba50e413f2fa7df32e8a0eac9542f/setup.py#L36>`_ and running against `my code <https://github.com/wimglenn/advent-of-code-wim/blob/master/aoc_wim/__init__.py>`_ (after ``pip install advent-of-code-wim``) would be like this:

.. code-block:: python

    >>> puzzle = Puzzle(year=2018, day=10)
    >>> puzzle.solve_for("wim")
    ('XLZAKBGZ', '10656')


If you've never written a plugin before, see https://entrypoints.readthedocs.io/ for more info about plugin systems based on Python entry-points.


Verify your code against multiple different inputs
--------------------------------------------------

*New in version 0.8.0.*

Ever tried running your code against other people's inputs? AoC is full of tricky edge cases. You may find that sometimes you're only getting the right answer by luck, and your code will fail on some other dataset. Using aocd, you can collect a few different auth tokens for each of your accounts (github/google/reddit/twitter) and verify your answers across multiple datasets.

To see an example of how to setup the entry-point for your code, look at `advent-of-code-sample <https://github.com/wimglenn/advent-of-code-sample>`_ for some inspiration. After dumping a bunch of session tokens into ``~/.config/aocd/tokens.json`` you could do something like this by running the ``aoc`` console script:

.. image:: https://user-images.githubusercontent.com/6615374/52138567-26e09f80-2613-11e9-8eaf-c42757bc9b86.png

As you can see above, I actually had incorrect code for `2017 Day 20: Particle Swarm <https://adventofcode.com/2017/day/20>`_, but that `bug <https://github.com/wimglenn/advent-of-code-wim/commit/31e454270001c6d06b46014fe5dafd03e29507b8>`_ only showed up for the google token's dataset. Whoops. Also, it looks like my algorithm for `2017 Day 13: Packet Scanners <https://adventofcode.com/2017/day/13>`_ was kinda garbage. Too slow. According to `AoC FAQ <https://adventofcode.com/about>`_:

  *every problem has a solution that completes in at most 15 seconds on ten-year-old hardware*

By the way, the ``aoc`` runner will kill your code if it takes more than 60 seconds, you can increase/decrease this by passing a command-line option, e.g. ``--timeout=120``.

*New in version 1.1.0:*  Added option ``--quiet`` to suppress any output from plugins so it doesn't mess up the ``aoc`` runner's display.


How does this library work?
---------------------------

It will automatically get today's data at import time, if used within the 
interactive interpreter.  Otherwise, the date is found by introspection of the
path and file name from which ``aocd`` module was imported.  

This means your filenames should be something sensible. The examples below
should all parse correctly, because they have digits in the path that are
unambiguously recognisable as AoC years (2015+) or days (1-25).

.. code-block::

   q03.py 
   xmas_problem_2016_25b_dawg.py
   ~/src/aoc/2015/p8.py

A filename like ``problem_one.py`` will not work, so don't do that.  If
you don't like weird frame hacks, just use the ``aocd.get_data()`` function 
instead and have a nice day!


Cache invalidation?
-------------------

``aocd`` saves puzzle inputs, answers, names, and your bad guesses to avoid hitting
the AoC servers any more often than strictly necessary (this also speeds things up).
All data is persisted in plain text files under ``~/.config/aocd``. To remove any
caches, you may simply delete whatever files you want under that directory tree.
If you'd prefer to use a different path, then export an ``AOCD_DIR`` environment
variable with the desired location.

*New in version 1.1.0:* By default, your token files are also stored under ``~/.config/aocd``.
If you want the token(s) and cached inputs/answers to exist in separate locations, you can set
the environment variable ``AOCD_CONFIG_DIR`` to specify a different location for the token(s).
