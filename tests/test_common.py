import py
import pytest

import fret.common as common


def _get_model_cls(name):
    return {'ModelTest': ModelTest}[name]


common.Workspace._get_model_cls = _get_model_cls


class ModelTest(common.Model):
    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('-x', type=int, required=True)
        parser.add_argument('-y', type=int, default=10)


def test_model():
    model1 = ModelTest.parse(['-x', '10'])
    model2 = ModelTest.build(x=10, y=10)
    assert model1.config == model2.config

    with pytest.raises(common.ParseError) as e:
        ModelTest.parse([])

    assert str(e.value) == 'the following arguments are required: -x'

    config = {'a.b': {'c.d': 10, 'c.e': 20}}
    common.Model._unfold_config(config)
    assert config == {'a': {'b': {'c': {'d': 10, 'e': 20}}}}


def test_workspace(tmpdir: py.path.local):
    ws = common.Workspace(str(tmpdir.join('ws')), ModelTest, {'x': 3, 'y': 4})
    assert str(ws.log_path) == str(tmpdir.join('ws/log'))
    assert str(ws.result_path) == str(tmpdir.join('ws/result'))
    assert str(ws.snapshot_path) == str(tmpdir.join('ws/snapshot'))
    assert ws.config == {'x': 3, 'y': 4}

    # test logging utilities
    logger = ws.logger('test')
    logger.error('test log')
    assert (ws.log_path / 'test.log').exists()

    logger = ws.logger('test')
    logger.error('test log 2')
    assert len(list((ws.log_path / 'test.log').open())) == 2

    ws = common.Workspace(str(tmpdir.join('ws')))
    assert ws.config == {'x': 3, 'y': 4}

    ws2 = common.Workspace(str(tmpdir.join('ws2')))
    ws2.setup_like(ws.build_model())
    assert str(ws2.build_model()) == 'ModelTest(x=3, y=4)'
