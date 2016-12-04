Advent of Code data
===================

|pyversions|_ |pypi|_ |womm|_

.. |pyversions| image:: https://img.shields.io/pypi/pyversions/advent-of-code-data.svg
.. _pyversions: 

.. |pypi| image:: https://img.shields.io/pypi/v/advent-of-code-data.svg
.. _pypi: https://pypi.python.org/pypi/advent-of-code-data

.. |womm| image:: https://cdn.rawgit.com/nikku/works-on-my-machine/v0.2.0/badge.svg
.. _womm: https://github.com/nikku/works-on-my-machine

Get your puzzle data with a single import statement:

.. code-block:: python

   from aocd import data

Might be useful for lazy Pythonistas and speedhackers.  


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

*Note:* If you don't like the env var, you could also put into a file 
``my_session.txt`` in your working directory.


How does it work?
-----------------

This is done by introspection of the path and file name from which ``aocd`` 
module was imported.  

This means your filenames should be something sensible.  The examples below
should all parse correctly:

.. code-block::

   q03.py 
   xmas_problem_2016_25b_dawg.py
   ~/src/aoc/2015/p8.py

A filename like ``problem_one.py`` will break shit, so don't do that.  If 
you don't like weird frame hacks, just use the ``aocd.get_data()`` function 
instead and have a nice day!

*Please be aware that Python will not import the same module twice, so if you 
need to get puzzle for multiple problems from within the same interpreter 
session then you will need to use the function directly rather than using the 
import-time magic.*

.. code-block:: python

   >>> from aocd import get_data
   >>> get_data(day=2)
   'UULDRRRDDLRLURUUURUURDRUURRDRRURUD...
   >>> get_data(day=24, year=2015)
   '1\n2\n3\n7\n11\n13\n17\n19\n23\n31...
