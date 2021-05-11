"""
Example main.py
"""

import sys

from os.path import dirname, realpath
from logging import DEBUG

from looksee import Scanner


# add the directory containing main.py (this file) to the Python module path,
# as it contains our fictitious "pooply" package.
sys.path.append(dirname(realpath(__file__)))


# initialize a scanner that scans a fictituous "pooply"
# package for dict objects containing an "id" key.
scanner = Scanner(
    predicate=lambda value: isinstance(value, dict) and 'public_id' in value,
    callback=lambda name, value, ctx: ctx.update({name: value}),
)


# for example's sake, set log level to DEBUG from default of INFO
scanner.log.set_level(DEBUG)


# scan the "pooply" package for dicts containing an "id" key.
found = scanner.scan('pooply')


# display the objects returned from the scan.
for name, value in found.items():
    scanner.log.info(f'Found {name}: {value}')
