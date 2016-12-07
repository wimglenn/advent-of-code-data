import re
from setuptools import setup


classifiers = [
    'Intended Audience :: Developers',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: MIT License',
    'Topic :: Software Development :: Libraries',
    'Topic :: Games/Entertainment :: Puzzle Games',
]

with open('README.rst') as f:
    long_description = f.read()

def get_version():
    with open('aocd.py') as f:
        [version] = re.findall(r"\n__version__ = '([0-9\.]*)'\n", f.read())
    return version

setup(
    name='advent-of-code-data',
    version=get_version(),
    description='Get your puzzle data with a single import',
    long_description=long_description,
    py_modules=['aocd'],
    author='Wim Glenn',
    author_email='hey@wimglenn.com',
    license='MIT',
    url='https://github.com/wimglenn/advent-of-code-data',
    classifiers=classifiers,
    install_requires=['pytz', 'requests', 'termcolor'],
)
