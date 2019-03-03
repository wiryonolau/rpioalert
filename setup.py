import os
import subprocess
from setuptools import setup, find_packages
from os.path import basename, dirname, join, splitext
from glob import glob

with open('./VERSION') as f:
    version = f.readline()

# Run with
# python3 setup.py sdist bdist_wheel
setup(name='rpioalert',
    version=version,
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'rpioalert=rpioalert.__main__:main',
        ]
    }
)
