import py
import pytest

import fret.common as common


def _get_model_cls(name):
    return {'ModelTest': ModuleTest}[name]


common.Workspace._get_module_cls = _get_model_cls


@common.configurable
class ModuleTest:
    def __init__(self,
                 x=(('required', True), ('type', int)),
                 y=4):
        pass


def test_model():
    model1 = ModuleTest.parse(['-x', '10'])
    model2 = ModuleTest(x=10, y=4)
    assert model1.config == model2.config

    with pytest.raises(common.ParseError) as e:
        ModuleTest.parse([])

    assert str(e.value) == 'the following arguments are required: -x'


def test_workspace(tmpdir: py.path.local):
    ws = common.Workspace(str(tmpdir.join('ws')))
    assert str(ws.log_path) == str(tmpdir.join('ws/log'))
    assert str(ws.result_path) == str(tmpdir.join('ws/result'))
    assert str(ws.snapshot_path) == str(tmpdir.join('ws/snapshot'))

    # test logging utilities
    logger = ws.logger('test')
    logger.error('test log')
    assert (ws.log_path / 'test.log').exists()

    logger = ws.logger('test')
    logger.error('test log 2')
    assert len(list((ws.log_path / 'test.log').open())) == 2
