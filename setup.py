from setuptools import setup

classifiers = [
    'Intended Audience :: Developers',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: MIT License',
    'Topic :: Software Development :: Libraries',
    'Topic :: Games/Entertainment :: Puzzle Games',
]

with open("README.rst") as f:
    long_description = f.read()

setup(
    name='advent-of-code-data',
    version='0.3.2',
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
