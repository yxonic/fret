import os
from contextlib import contextmanager

from fret.app import App, get_app, set_global_app
from fret.cli import main
import py
import pytest

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
        assert app.main(['config']) is not None
        app.main(['clean', '-c'])
        with pytest.raises(SystemExit):
            app.main(['run'])


@contextmanager
def chapp(appdir):
    _app = get_app()
    _cwd = os.getcwd()
    appdir = str(appdir)
    app = App()
    os.chdir(appdir)
    set_global_app(app)
    try:
        yield app
    finally:
        set_global_app(_app)
        os.chdir(_cwd)
