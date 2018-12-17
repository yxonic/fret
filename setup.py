#!/usr/bin/env python
from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='fret',
    version='0.1.1.post4',
    url='https://github.com/yxonic/fret',
    license='MIT',
    author='yxonic',
    author_email='yxonic@gmail.com',
    description='REProducible Experimental environment.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=['fret'],
    platforms='any',
    python_requires='>=3.4',
    install_requires=[
        'toml',
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-cov',
            'pytest-pep8',
        ],
        'docs': [
            'sphinx',
            'sphinx-rtd-theme',
        ]
    },
    entry_points={
        'console_scripts': [
            'fret = fret.cli:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
    ],
)
