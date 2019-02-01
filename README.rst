Advent of Code data
===================

|pyversions|_ |pypi|_ |womm|_ |travis|_

.. |pyversions| image:: https://img.shields.io/pypi/pyversions/advent-of-code-data.svg
.. _pyversions: 

.. |pypi| image:: https://img.shields.io/pypi/v/advent-of-code-data.svg
.. _pypi: https://pypi.org/project/advent-of-code-data/

.. |womm| image:: https://cdn.rawgit.com/nikku/works-on-my-machine/v0.2.0/badge.svg
.. _womm: https://github.com/nikku/works-on-my-machine

.. |travis| image:: https://img.shields.io/travis/wimglenn/advent-of-code-data.svg?branch=master
.. _travis: https://travis-ci.com/wimglenn/advent-of-code-data


Get your puzzle data with a single import statement:

.. code-block:: python

   from aocd import data

Might be useful for lazy Pythonistas and speedhackers.  

**Note:  Please use version 0.3+ of this library.**  It memoizes successful
requests client side and rate-limits the get_data function, as
`requested by the AoC author <https://www.reddit.com/r/adventofcode/comments/3v64sb/aoc_is_fragile_please_be_gentle/>`_.
Thanks!


Automated submission
--------------------

*New in version 0.4.0.* Basic use:

.. code-block:: python

   from aocd import submit
   submit(my_answer, level=1, day=25, year=2017)

Note that the same filename introspection of year/day also works for automated
submission. There's also introspection of the "level", i.e. part 1 or part 2,
aocd can automatically determine if you have already completed part 1 or not,
and submit an answer for the correct part accordingly. In this case, just use:

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
    >>> puzzle.input_data
    'p=<-1027,-979,-188>, v=<7,60,66>, a=<9,1,-7>\np=<-1846,-1539,-1147>, v=<88,145,67>, a=<6,-5,2> ...

Submitting answers is also by regular attribute access. Any incorrect answers you submitted are remembered, and aocd will prevent you from attempting to submit the same incorrect value twice:

.. code-block:: python

    >>> puzzle.answer_a = 299
    That's not the right answer; your answer is too high. If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit. Please wait one minute before trying again. (You guessed 299.) [Return to Day 20]
    >>> puzzle.answer_a = 299
    aocd will not submit that answer again. You've previously guessed 299 and the server responded:
    That's not the right answer; your answer is too high. If you're stuck, there are some general tips on the about page, or you can ask for hints on the subreddit. Please wait one minute before trying again. (You guessed 299.) [Return to Day 20]

Solutions can be executed using `setuptools style plugins <https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins>`_ for your code, i.e. the ``pkg_resources`` "entry-points". My entry-point name is "wim" so an example for running `my code <https://github.com/wimglenn/advent-of-code-wim/blob/master/setup.py#L30>`_ (after ``pip install advent-of-code-wim``) would be:

.. code-block:: python

    >>> puzzle = Puzzle(year=2018, day=10)
    >>> puzzle.solve_for("wim")
    ('XLZAKBGZ', '10656')


Verify your code against multiple different inputs
--------------------------------------------------

*New in version 0.8.0.*

Ever tried running your code against other people's inputs? AoC is full of tricky edge cases. You may find that sometimes you're only getting the right answer by luck, and your code will fail on some other dataset. Using aocd, you can collect a few different auth tokens for each of your accounts (github/google/reddit/twitter) and verify your answers across multiple datasets.

To see an example of how to setup the entry-point for your code, look at `advent-of-code-sample <https://github.com/wimglenn/advent-of-code-sample>`_. After dumping a bunch of session tokens into ``~/.config/aocd/tokens.json`` you could do something like this by running the ``aoc`` console script:

.. image:: https://user-images.githubusercontent.com/6615374/52112948-a0559f00-25cd-11e9-88f7-181bd5d9b9f6.png

As you can see above, I've actually got an incorrect code for `2017/day20 <https://adventofcode.com/2017/day/20>`_, but that bug only showed up for google token's dataset. Whoops. Also, it looks like my algorithm for `2017/day13 <https://adventofcode.com/2017/day/13>`_ was kinda garbage. Too slow. According to `AoC FAQ <https://adventofcode.com/about>`_:

> *every problem has a solution that completes in at most 15 seconds on ten-year-old hardware*

Therefore, ``aoc`` script will kill your code if it takes more than 60 seconds, you can increase/decrease this by passing a command-line option, e.g. ``--timeout=120`` (seconds).


Setup Guide
-----------

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

*Note:* If you don't like the env var, you could also put into a text file 
in your home directory (use the filename ``~/.config/aocd/token``).


How does it work?
-----------------

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

.. code-block:: python

   >>> from aocd import get_data
   >>> get_data(day=2)
   'UULDRRRDDLRLURUUURUURDRUURRDRRURUD...
   >>> get_data(day=24, year=2015)
   '1\n2\n3\n7\n11\n13\n17\n19\n23\n31...
