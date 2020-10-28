import os

import py
import pytest

import fret
import fret.common
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
@fret.configurable(submodules=['sub'], build_subs=False)
class C:
    def __init__(self, sub, c):
        self.sub = sub()
        assert sub.help


# noinspection PyUnusedLocal
@fret.configurable(submodules=['sub'])
class D:
    def __init__(self, sub):
        self.sub = sub


def test_module():
    c = D(A())
    assert c.sub.config == {'a': 0}
    with pytest.raises(fret.common.NoWorkspaceError):
        _ = c.ws


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
        ws.register('main', A(a=1))

        ws.register('sub', B, b=2)

        ws.register('main', D)
        model = ws.build()
        assert model.sub.config.b == 2

        ws.register('main', C)

        with pytest.raises(TypeError):
            ws.build()

        main = ws.build(c=3)  # env: a=1, b=2; build spec: c=3
        assert main.ws == ws
        ws.save(main, 'tag1')

        ws.register('sub', B, b=4)
        ws.save(main, str(tmpdir.join('tag2.pt')))

        main_ = ws.load(tag='tag1')
        assert main_.sub.config == main.sub.config
        main_ = ws.load(path=str(tmpdir.join('tag2.pt')))
        assert main_.sub.config.b == 4

        logger = ws.logger('foo')
        logger.warning('test log')
        assert ws.log('foo.log').exists()
        assert 'test log' in ws.log('foo.log').open().read()

    # same ws configuration -> same build behavior
    ws = fret.workspace(str(tmpdir.join('ws')))
    main_ = ws.build(c=3)
    assert ws.config_dict()['sub']['b'] == 4
    assert main_.sub.config.b == 4
    logger_ = ws.logger('foo')
    assert logger == logger_

    # persistency: ws.run context manager
    with ws.run('test-1') as run:
        rid = run.id
        assert rid.startswith('test-1')
        assert run.log().is_dir()
        assert run.result().is_dir()
        assert run.snapshot().is_dir()
        x = run.value(3)
        assert x == 3
        s = run.acc()
        s += 1
        assert s.sum() == 1

        for i in fret.util.nonbreak(run.range(10)):
            if i == 5:
                break

    with ws.run('test-1') as run:
        assert run.id == rid
        x = run.value(5)
        assert x == 3
        s = run.acc()
        s += 2
        assert s.sum() == 3

        for i in fret.util.nonbreak(run.range(10)):
            assert i == 6
            break

    with ws.run('test-2') as run:
        assert run.id != rid
        rid = run.id
        x = run.value(5)
        assert x == 5
        s = run.acc()
        s += 2
        assert s.sum() == 2
        for i in run.brange(10):
            if i == 5:
                break

    with ws.run('test-2') as run:
        assert run.id == rid
        x = run.value(5)
        s = run.acc()
        s += 2
        assert s.sum() == 4
        for i in run.brange(10):
            assert i == 5
            break

    with ws.run('test-2') as run:
        x = run.value(5)
        s = run.acc()
        r = iter(run.brange(20))
        first = next(r)
        last = 0
        for i in r:
            last = i
        assert first == 5
        assert last == 19
