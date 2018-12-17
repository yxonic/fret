import os

import py
import pytest

import fret


@fret.configurable
class ModuleTest:
    def __init__(self, x=(('required', True), ('type', int)), y=4):
        pass


@fret.configurable
class SubModuleTest:
    def __init__(self, sub, z=5):
        pass


def test_module():
    model1 = ModuleTest.parse(['-x', '10'])
    model2 = ModuleTest(x=10, y=4)
    assert model1.config == model2.config

    with pytest.raises(fret.ParseError) as e:
        ModuleTest.parse([])

    assert str(e.value) == 'the following arguments are required: -x'


def test_workspace(tmpdir: py.path.local):
    ws = fret.Workspace(str(tmpdir.join('ws')))
    assert os.path.samefile(str(ws.path), str(tmpdir.join('ws')))
    assert os.path.samefile(str(ws.log_path), str(tmpdir.join('ws/log')))
    assert os.path.samefile(str(ws.result_path),
                            str(tmpdir.join('ws/result')))
    assert os.path.samefile(str(ws.checkpoint_path),
                            str(tmpdir.join('ws/checkpoint')))

    # test logging utilities
    logger = ws.logger('test')
    logger.error('test log')
    assert (ws.log_path / 'test.log').exists()

    logger = ws.logger('test')
    logger.error('test log 2')
    assert len(list((ws.log_path / 'test.log').open())) == 2

    ws.add_module('main', ModuleTest, dict(x=3, y=4))
    module = ws.build_module()
    assert str(module.config) == 'ModuleTest(x=3, y=4)'

    ws.save()
    ws2 = fret.Workspace(str(tmpdir.join('ws')))
    print(fret.common.app)
    assert ws.get_module('main') == ws2.get_module('main')

    with pytest.raises(fret.NotConfiguredError) as e:
        ws.build_module('wrong')
    assert str(e.value) == 'module wrong not configured'

    ws.add_module('test', SubModuleTest.parse([]))
    ws.add_module('sub', ModuleTest, dict(x=3, y=4))

    assert str(ws.build_module('test')) == \
        'SubModuleTest(sub=ModuleTest(x=3, y=4), z=5)'
