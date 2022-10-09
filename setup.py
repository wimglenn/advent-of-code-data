import os
from setuptools import setup


src_version = os.path.join(os.path.dirname(__file__), "aocd", "version.py")
with open(src_version) as f:
    version = f.read().strip().split()[-1][1:-1]


setup(
    name="advent-of-code-data",
    version=version,
    description="Get your puzzle data with a single import",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    packages=["aocd"],
    entry_points={
        "console_scripts": [
            "aocd=aocd.cli:main",
            "aoc=aocd.runner:main",
            "aocd-token=aocd.cookies:scrape_session_tokens"
        ],
        # https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins
        "adventofcode.user": [],
    },
    author="Wim Glenn",
    author_email="hey@wimglenn.com",
    license="MIT",
    url="https://github.com/wimglenn/advent-of-code-data",
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries",
        "Topic :: Games/Entertainment :: Puzzle Games",
    ],
    install_requires=[
        "python-dateutil",
        "requests",
        "termcolor",
        "beautifulsoup4",
        "pebble",
        'colorama; platform_system == "Windows"',
        "tzlocal",
    ],
    options={"bdist_wheel": {"universal": "1"}},
)
