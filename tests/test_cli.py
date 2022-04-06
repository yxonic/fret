import importlib
import os

from fret.cli import main
import py
import pytest


code0 = '''
import nothing
'''

code1 = '''
import fret

@fret.configurable
class Model:
    def __init__(self, x=(3, 'x'),
                 y=fret.argspec(default=4, type=int)):
        ...

@fret.command
def run(ws):
    model = ws.build()
    print(model)
    return model
'''

code2 = '''
import fret

@fret.command
def train(ws):
    model = ws.build()
    model.train()
    ws.save(model, 'trained')

@fret.command
def test(ws):
    model = ws.load(path='ws/best/snapshot/main.trained.pt')
    print(model.weight)
    return model

@fret.configurable(states=['weight'])
class Model:
    def __init__(self):
        self.weight = 0
    def train(self):
        self.weight = 23
'''

code3 = '''
import fret

@fret.configurable(states=['weight'])
def Model():
    def __init__(self):
        self.weight = 0
    def train(self):
        self.weight = 23
'''

code4 = '''
import fret

@fret.command
class Model:
    def __init__(self):
        self.weight = 0
    def train(self):
        self.weight = 23
'''


def test_main(tmpdir: py.path.local, caplog):
    with pytest.raises(SystemExit):
        main()

    caplog.clear()

    # error test
    appdir = tmpdir.join('appdir0')
    appdir.mkdir()
    os.chdir(str(appdir))

    with appdir.join('main.py').open('w') as f:
        f.write(code0)

    with pytest.raises(ImportError):
        import fret.app
        assert fret.app

    with appdir.join('main.py').open('w') as f:
        f.write(code3)

    with pytest.raises(TypeError):
        import fret.app
        assert fret.app

    with appdir.join('main.py').open('w') as f:
        f.write(code4)

    with pytest.raises(TypeError):
        import fret.app
        assert fret.app

    # simple app test
    appdir = tmpdir.join('appdir1')
    appdir.mkdir()
    os.chdir(str(appdir))

    with appdir.join('main.py').open('w') as f:
        f.write(code1)

    import fret.app
    main('config Model'.split())
    model = main(['run'])
    assert model.config.x == 3

    main('config Model -x 5 -y 10'.split())
    model = main(['run'])
    assert model.config.x == 5
    assert model.config.y == 10

    assert main(['config']) is not None

    main(['clean', '-c', '-f'])
    with pytest.raises(SystemExit):
        main(['run'])

    with pytest.raises(SystemExit):
        assert main(['config']) is None

    main('-w ws/model1 config Model'.split())
    main('-w ws/model2 config Model -x 5 -y 10'.split())
    model = main('-w ws/model1 run'.split())
    assert model.config.x == 3
    model = main('-w ws/model2 run'.split())
    assert model.config.x == 5

    appdir.join('fret.toml').open('w').close()

    os.chdir(str(appdir.join('ws/model2')))
    importlib.reload(fret)
    importlib.reload(fret.app)

    model = main(['run'])
    assert model.config.x == 5

    # appdir = tmpdir.join('appdir2')
    # appdir.mkdir()

    # with appdir.join('main.py').open('w') as f:
    #     f.write(code2)
    # with appdir.join('app.py').open('w') as f:
    #     f.write(code1)

    # os.chdir(str(appdir))
    # del sys.modules['main']
    # del fret.app._module
    # importlib.reload(fret)
    # importlib.reload(fret.app)

    # main('-w ws/best config Model'.split())
    # main('-w ws/best train'.split())
    # model = main(['test'])
    # assert model.weight == 23

    # os.environ['FRETAPP'] = 'app'
    # importlib.reload(fret)
    # importlib.reload(fret.app)

    # main('config Model'.split())
    # model = main('run'.split())
    # del os.environ['FRETAPP']
    # assert model.config.x == 3
