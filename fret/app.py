import os
import sys
import pathlib
import importlib
import toml

from .common import NoAppError, commands
from .util import _dict, Configuration


# load configuration
_p = pathlib.Path().absolute()
if _p.joinpath('fret.toml').exists():
    _path = _p
else:
    while _p != _p.parent:
        if _p.joinpath('fret.toml').exists():
            _path = _p
            break
        _p = _p.parent
    else:
        _path = pathlib.Path().absolute()

root = str(_path)

_cfg_path = _path / 'fret.toml'
if _cfg_path.exists():
    _cfg = toml.load(_cfg_path.open())
else:
    _cfg = _dict()
config = Configuration(_cfg)

# import modules
sys.path.insert(0, root)
appname = os.environ.get('FRETAPP')
_module = None

if appname is not None:
    _module = importlib.import_module(appname)
elif 'appname' in config:
    _module = importlib.import_module(config.appname)
else:
    for appname in ['main', 'app']:
        try:
            _module = importlib.import_module(appname)
            break
        except ImportError as _e:
            if _e.name != appname:
                sys.path.remove(root)
                raise
    else:
        sys.path.remove(root)
        raise NoAppError('cannot find app to import')

if 'import_modules' in config:
    for m in config.import_modules:
        importlib.import_module(m)

sys.path.remove(root)


# expose commands
for _name, _cmd in commands.items():
    globals()[_name] = _cmd
del _name, _cmd

__all__ = ['root', 'config']
