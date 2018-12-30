Advent of Code data
===================

|pyversions|_ |pypi|_ |womm|_

.. |pyversions| image:: https://img.shields.io/pypi/pyversions/advent-of-code-data.svg
.. _pyversions: 

.. |pypi| image:: https://img.shields.io/pypi/v/advent-of-code-data.svg
.. _pypi: https://pypi.org/project/advent-of-code-data/

.. |womm| image:: https://cdn.rawgit.com/nikku/works-on-my-machine/v0.2.0/badge.svg
.. _womm: https://github.com/nikku/works-on-my-machine

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

New in version 0.4.0. Basic use:

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
