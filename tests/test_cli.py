import importlib
import os
from contextlib import contextmanager

from fret.app import App, get_app, set_global_app
from fret.cli import main
import py
import pytest


@contextmanager
def chapp(appdir):
    _app = get_app()
    _cwd = os.getcwd()
    appdir = str(appdir)
    os.chdir(appdir)
    app = App()
    set_global_app(app)
    imp = app.import_modules()
    if imp:
        try:
            importlib.reload(imp)
        except (ImportError, AttributeError):
            pass
    try:
        yield app
    finally:
        set_global_app(_app)
        os.chdir(_cwd)


code1 = '''
import fret

@fret.configurable
class Model:
    def __init__(self, x=3, y=4):
        ...

@fret.command
def run(ws):
    model = ws.build()
    print(model)
    return model
'''


def test_main(tmpdir: py.path.local):
    with pytest.raises(SystemExit):
        main()

    appdir = tmpdir.join('appdir1')
    appdir.mkdir()

    with appdir.join('main.py').open('w') as f:
        f.write(code1)

    with chapp(appdir) as app:
        app.main(['config', 'Model'])
        model = app.main(['run'])
        assert model.config.x == 3

        app.main(['config', 'Model', '-x', '5', '-y', '10'])
        model = app.main(['run'])
        assert model.config.x == 5
        assert model.config.y == 10

        assert app.main(['config']) is not None

        app.main(['clean', '-c'])
        with pytest.raises(SystemExit):
            app.main(['run'])

        with pytest.raises(SystemExit):
            assert app.main(['config']) is None

        app.main(['-w', 'ws/model1', 'config', 'Model'])
        app.main(['-w', 'ws/model2', 'config', 'Model', '-x', '5', '-y', '10'])
        model = app.main(['-w', 'ws/model1', 'run'])
        assert model.config.x == 3
        model = app.main(['-w', 'ws/model2', 'run'])
        assert model.config.x == 5

    appdir.join('fret.toml').open('w').close()
    with chapp(appdir.join('ws/model2')) as app:
        model = app.main(['run'])
        assert model.config.x == 5
