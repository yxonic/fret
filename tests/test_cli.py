import fret
from fret.cli import main
import pytest


# noinspection PyUnusedLocal
@fret.configurable
class A:
    def __init__(self, a):
        pass


# noinspection PyUnusedLocal
@fret.configurable
class B(A):
    def __init__(self, b, **others):
        super().__init__(**others)


# noinspection PyUnusedLocal
@fret.configurable(submodules=['sub'])
class C:
    def __init__(self, sub, c):
        self.b = sub()


def test_main():
    with pytest.raises(SystemExit):
        main()
