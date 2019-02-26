import os

import py
import pytest

import fret


# noinspection PyUnusedLocal
@fret.configurable
class A:
    def __init__(self, a):
        pass


# noinspection PyUnusedLocal
@fret.configurable
class B:
    def __init__(self, b):
        pass


# noinspection PyUnusedLocal
@fret.configurable(submodules=['sub'])
class C:
    def __init__(self, sub, c):
        self.b = sub()


def test_module():
    pass


def test_workspace(tmpdir: py.path.local):
    ws = fret.workspace(str(tmpdir.join('ws')))
    assert ws.path.is_dir()
    assert os.path.samefile(str(ws.path), str(tmpdir.join('ws')))

    # test file utilities
    directory = ws.log('test/')
    assert directory.is_dir()
    assert os.path.samefile(str(directory), str(tmpdir.join('ws/log/test/')))

    file = ws.result('test/test.txt')
    file.open('w').close()
    assert os.path.samefile(str(file),
                            str(tmpdir.join('ws/result/test/test.txt')))
    assert file.exists()

    with pytest.raises(FileNotFoundError):
        ws.checkpoint('duck.pt').open()
    ws.checkpoint('duck.pt').open('w').close()
    assert os.path.samefile(str(ws.checkpoint('duck.pt')),
                            str(tmpdir.join('ws/checkpoint/duck.pt')))

    # test module registering
    ws.register(A(a=1))

    ws.register('sub', B, b=2)
    ws.register(C)

    with pytest.raises(TypeError):
        ws.build()

    # reproducibility and persistency
    # rules:
    # 1. same ws configuration -> same build behavior
    # 2. submodule and builder relies on current workspace configuration
    # 3. save and load: ws configuration + build spec + state
    main = ws.build(c=3)  # env: a=1, b=2; build spec: c=3
    ws.save(main, 'tag1')

    ws.register('sub', B, b=4)
    ws.save(main, 'tag2')

    main_ = ws.load('tag1')
    assert main_.b.config == main.b.config
    main_ = ws.load('tag2')
    assert main_.b.config.b == 4

    ws_ = fret.workspace(str(tmpdir.join('ws')))
    main_ = ws_.build(c=3)
    assert main_.b.config.b == 4

    # persistency: ws.run context manager
    with ws.run('test') as run:
        rid = run.id
        assert rid.startswith('test')
        assert run.checkpoint().is_dir()

    with ws.run('test') as run:
        assert run.id == rid

    with ws.run('test', resume=False) as run:
        assert run.id != rid
        rid = run.id

    with ws.run('test') as run:
        assert run.id == rid
