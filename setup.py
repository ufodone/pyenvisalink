#!/usr/bin/env python3
from setuptools import setup

setup(
    name="pyenvisalink",
    version="5.0.0b1",
    description=(
        "A python3 library for running asynchronus communications with envisalink "
        "alarm control panel modules."
    ),
    long_description=(
        "A python3 library for running asynchronus communications with envisalink "
        "alarm control panel modules."
    ),
    url="https://github.com/ufodone/pyenvisalink",
    author="David O'Neill",
    author_email="ufodone@gmail.com",
    license="MIT",
    packages=["pyenvisalink"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.10",
    ],
)
