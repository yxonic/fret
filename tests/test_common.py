import os

import py
import pytest

import fret
import fret.util


# noinspection PyUnusedLocal
@fret.configurable
class A:
    def __init__(self, a=0):
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


def test_module():
    pass


def test_workspace(tmpdir: py.path.local):
    # reproducibility and persistency
    # rules:
    # 1. same ws configuration -> same build behavior
    # 2. submodule and builder relies on current workspace configuration
    # 3. save and load: ws configuration + build spec + state
    with fret.workspace(str(tmpdir.join('ws'))) as ws:
        assert ws.path.is_dir()
        assert os.path.samefile(str(ws.path), str(tmpdir.join('ws')))

        # test file utilities
        directory = ws.log('test/')
        assert directory.is_dir()
        assert os.path.samefile(str(directory),
                                str(tmpdir.join('ws/log/test/')))

        file = ws.result('test/test.txt')
        file.open('w').close()
        assert os.path.samefile(str(file),
                                str(tmpdir.join('ws/result/test/test.txt')))
        assert file.exists()

        with pytest.raises(FileNotFoundError):
            ws.snapshot('duck.pt').open()
        ws.snapshot('duck.pt').open('w').close()
        assert os.path.samefile(str(ws.snapshot('duck.pt')),
                                str(tmpdir.join('ws/snapshot/duck.pt')))

        # test module registering
        ws.register(A(a=1))

        ws.register('sub', B, b=2)
        ws.register(C)

        with pytest.raises(TypeError):
            ws.build()

        main = ws.build(c=3)  # env: a=1, b=2; build spec: c=3
        ws.save(main, 'tag1')

        ws.register('sub', B, b=4)
        ws.save(main, 'tag2')

        main_ = ws.load('tag1')
        assert main_.b.config == main.b.config
        main_ = ws.load('tag2')
        assert main_.b.config.b == 4

    # same ws configuration -> same build behavior
    ws = fret.workspace(str(tmpdir.join('ws')))
    main_ = ws.build(c=3)
    assert main_.b.config.b == 4

    # persistency: ws.run context manager
    with ws.run('test') as run:
        rid = run.id
        assert rid.startswith('test')
        assert run.snapshot().is_dir()
        x = run.value(3)
        assert x == 3
        s = run.acc()
        s += 1
        assert s.sum() == 1

        for i in fret.util.nonbreak(run.range(10)):
            if i >= 5:
                break

    with ws.run('test') as run:
        assert run.id == rid
        x = run.value(5)
        assert x == 3
        s = run.acc()
        s += 2
        assert s.sum() == 3

        for i in fret.util.nonbreak(run.range(10)):
            assert i == 6
            break

    with ws.run('test', resume=False) as run:
        assert run.id != rid
        rid = run.id
        x = run.value(5)
        assert x == 5
        s = run.acc()
        s += 2
        assert s.sum() == 2

        for i in fret.util.nonbreak(run.range(10)):
            assert i == 0
            break

    with ws.run('test') as run:
        assert run.id == rid
