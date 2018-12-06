#!/usr/bin/env python
from setuptools import setup

setup(
    name='repe',
    version='0.1',
    url='https://github.com/yxonic/repe',
    license='MIT',
    author='yxonic',
    author_email='yxonic@gmail.com',
    description='REProducible Experimental environment.',
    packages=['repe'],
    platforms='any',
    python_requires='>=3.5',
    install_requires=[
        'toml'
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-cov',
            'pytest-pep8',
        ],
        'docs': [
            'sphinx',
        ]
    },
    entry_points={
        'console_scripts': [
            'repe = repe.cli:main',
        ],
    }
)
