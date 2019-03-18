#!/usr/bin/env python
from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

test_deps = [
    'pytest>=4',
    'pytest-cov>=2.6.0',
    'pytest-pep8>=1',
]

setup(
    name='fret',
    version='0.2.2',
    url='https://github.com/yxonic/fret',
    license='MIT',
    author='yxonic',
    author_email='yxonic@gmail.com',
    description='REProducible Experimental environment.',
    long_description=long_description,
    packages=['fret'],
    platforms='any',
    python_requires='>=3.4',
    install_requires=[
        'toml',
    ],
    tests_require=test_deps,
    extras_require={
        'test': test_deps,
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
