#!/usr/bin/env python
from setuptools import setup
import re

with open('fret/__init__.py') as f:
    version = re.search(r'__version__ = \'(.+)\'', f.read()).group(1)

with open('README.md') as f:
    long_description = f.read()

test_deps = [
    'pytest>=4',
    'pytest-cov>=2.6.0',
    'pytest-pep8>=1',
]
doc_deps = [
    'sphinx',
    'sphinx-rtd-theme',
    'recommonmark'
]
dev_deps = test_deps + doc_deps + [
    'setuptools>=40',
    'wheel'
]

setup(
    name='fret',
    version=version,
    url='https://github.com/yxonic/fret',
    license='MIT',
    author='yxonic',
    author_email='yxonic@gmail.com',
    description='Framework for Reproducible ExperimenTs.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['fret'],
    platforms='any',
    python_requires='>=3.4',
    install_requires=[
        'toml',
    ],
    tests_require=test_deps,
    extras_require={
        'test': test_deps,
        'doc': doc_deps,
        'dev': dev_deps
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
