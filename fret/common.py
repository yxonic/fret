import argparse
import inspect as ins
import logging
import pathlib
import pickle
from datetime import datetime

import toml

from .exceptions import NotConfiguredError, NoWorkspaceError
from .util import classproperty, Configuration, stateful, overload


class Workspace:
    """Workspace utilities. One can save/load configurations, build models
    with specific configuration, save snapshots, open results, etc., using
    workspace objects."""

    def __init__(self, app, path, config=None):
        self._app = app
        self._path = pathlib.Path(path)
        self._modules = {}
        if self.config_path.exists():
            conf = toml.load(self.config_path.open())
            for name, cfg in conf.items():
                cls_name = cfg['module']
                del cfg['module']
                self._modules[name] = (cls_name, cfg)
        if config:
            self._modules.update(config)

    @property
    def path(self):
        if not self._path.exists():
            self._path.mkdir(parents=True)
        return self._path

    @property
    def config_path(self):
        cp = self.path.joinpath('config.toml')
        return cp

    def log(self, *filename):
        path = self.path.joinpath('log', *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path

    def result(self, *filename):
        path = self.path.joinpath('result', *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path

    def snapshot(self, *filename):
        path = self.path.joinpath('snapshot', *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path

    @overload((..., str, ...), ...,
              (..., ...), lambda self, m: (self, 'main', m))
    def register(self, name, module, **kwargs):
        """Register and save module configuration."""
        if not ins.isclass(module):
            cfg = module.config._dict()
            cfg.update(kwargs)
            self._modules[name] = (module.__class__.__name__, cfg)
        else:
            self._modules[name] = (module.__name__, kwargs)

    def write(self):
        cfg = {name: dict({'module': cls_name}, **cfg)
               for name, (cls_name, cfg) in self._modules.items()}
        toml.dump(cfg, self.config_path.open('w'))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.write()

    def _try_get_module(self, name='main'):
        if name in self._modules:
            return self._modules[name]
        else:
            raise NotConfiguredError('module %s not configured' % name)

    def build(self, name='main', **kwargs):
        """Build module according to the configurations in current
        workspace."""
        cls_name, cfg = self._try_get_module(name)
        cfg = cfg.copy()
        cfg.update(kwargs)

        try:
            cls = self._app.load_module(cls_name)
        except KeyError:
            raise KeyError('definition of module %s not found', cls_name)

        for sub in cls.submodules:
            if sub not in cfg or isinstance(cfg[sub], str):
                if cls._init_subs:
                    cfg[sub] = self.build(cfg.get(sub) or sub)
                else:
                    cfg[sub] = Builder(self, cfg.get(sub) or sub)

        # noinspection PyCallingNonCallable
        obj = cls(**cfg)
        obj.ws = self
        obj.build_name = name
        if kwargs:
            obj.spec = Configuration(kwargs)
        return obj

    def save(self, obj, tag):
        env = self._modules
        args = obj.spec._dict() if hasattr(obj, 'spec') else {}
        state = obj.state_dict()
        if isinstance(tag, str) and not tag.endswith('.pt'):
            f = self.snapshot(obj.build_name + '.' + tag + '.pt')
        else:
            f = pathlib.Path(tag)
        pickle.dump({'env': env, 'args': args, 'state': state}, f.open('wb'))

    @overload((..., str, ...), ...,
              (..., ...), lambda self, t: (self, 'main', t))
    def load(self, name, tag):
        if isinstance(tag, str) and not tag.endswith('.pt'):
            f = self.snapshot(name + '.' + tag + '.pt')
        else:
            f = pathlib.Path(tag)
        state = pickle.load(f.open('rb'))
        last_ws = Workspace(self._app, self._path, state['env'])
        obj = last_ws.build(name, **state['args'])
        obj.load_state_dict(state['state'])
        return obj

    def logger(self, name: str):
        """Get a logger that logs to a file under workspace.

        Notice that same logger instance is returned for same names.

        Args:
            name(str): logger name
        """
        logger = logging.getLogger(name)
        if logger.handlers:
            # previously configured, remain unchanged
            return logger
        file_formatter = logging.Formatter('%(levelname)s [%(name)s] '
                                           '%(asctime)s %(message)s',
                                           datefmt='%Y-%m-%d %H:%M:%S')
        file_handler = logging.FileHandler(
            str(self.log(name + '.log')))
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        return logger

    def run(self, tag, resume=True):
        return Run(self, tag, resume)

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return 'Workspace(path=' + str(self.path) + ')'


class Run:
    """Class designed for running state persistency."""

    __slots__ = ['_ws', '_id', '_states', '_index']

    def __init__(self, ws, tag, resume):
        self._ws = ws
        self._id = None
        self._states = {}
        self._index = 0
        if resume:
            ids = [filename.name for filename in ws.snapshot().iterdir()
                   if filename.is_dir() and filename.name.startswith(tag)]
            if ids:
                self._id = max(ids)  # most recent
        if self._id is None:
            self._id = tag + '-' + datetime.now().strftime("%Y%m%d%H%M%S")
        if not resume:
            while ws.snapshot(self._id).exists():
                self._id = self._id + '_'

    def __enter__(self):
        # load state if possible
        state_file = self._ws.snapshot(self._id, '.states.pt')
        if state_file.exists():
            self._states = pickle.load(state_file.open('rb'))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        state_file = self._ws.snapshot(self._id, '.states.pt')
        for k in self._states:
            if hasattr(self._states[k], 'state_dict'):
                self._states[k] = self._states[k].state_dict()
        pickle.dump(self._states, state_file.open('wb'))

    @property
    def id(self):
        return self._id

    @overload((..., str, ...), ...,
              (..., ...), lambda self, m: (self, None, m))
    def value(self, name, value):
        if name is None:
            name = str(self._index)
            self._index += 1
        if name in self._states:
            return self._states[name]
        else:
            self._states[name] = value
            return value

    @overload((..., str, ...), ...,
              (..., None, ...), ...,
              (..., ...), lambda self, m: (self, None, m))
    def register(self, name, obj):
        if name is None:
            name = str(self._index)
            self._index += 1
        if name in self._states:
            obj.load_state_dict(self._states[name])

        self._states[name] = obj
        return obj

    @overload((..., str), ...,
              (...,), lambda self: (self, None))
    def acc(self, name):
        return self.register(name, Accumulator())

    @overload((..., str, int), ...,
              (..., str, int, int), ...,
              (..., str, int, int, int), ...,
              (..., int), lambda self, *args: (self, None) + args,
              (..., int, int), lambda self, *args: (self, None) + args,
              (..., int, int, int), lambda self, *args: (self, None) + args)
    def range(self, name, *args):
        return self.register(name, Range(*args))

    def log(self, *filename):
        path = self._ws.path.joinpath('log', self._id, *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path

    def result(self, *filename):
        path = self._ws.path.joinpath('result', self._id, *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path

    def snapshot(self, *filename):
        path = self._ws.path.joinpath('snapshot', self._id, *filename)
        _mkdir(path, not filename or filename[-1].endswith('/'))
        return path


@stateful
class Accumulator:
    """A stateful accumulator."""
    __slots__ = ['_sum', '_cnt']

    def __init__(self):
        self._sum = 0
        self._cnt = 0

    def __iadd__(self, other):
        self._sum += other
        self._cnt += 1
        return self

    def __int__(self):
        return int(self._sum)

    def __float__(self):
        return float(self._sum)

    def clear(self):
        self._sum = 0
        self._cnt = 0

    def sum(self):
        return self._sum

    def mean(self):
        return self._sum / self._cnt if self._cnt > 0 else self._sum


@stateful
class Range:
    """A stateful range object that mimics built-in ``range``."""
    __slots__ = ['start', 'step', 'stop', '_start']

    def __init__(self, *args):
        r = range(*args)
        self.start = r.start
        self.step = r.step
        self.stop = r.stop
        self._start = r.start

    def __iter__(self):
        for i in range(self.start, self.stop, self.step):
            self.start = i + self.step
            yield i

    def clear(self):
        self.start = self._start


class Builder:
    """Class for building a specific module, with preset ws configuration."""
    def __init__(self, ws, name):
        self.ws = ws
        self._name = name

    def __eq__(self, other):
        return self.ws._modules[self._name] == other.ws._modules[other._name]

    def __call__(self, **kwargs):
        return self.ws.build(self._name, **kwargs)

    def __str__(self):
        cls_name, cfg = self.ws._modules[self._name]
        return cls_name + '(' + str(Configuration(cfg)) + ')'

    def __repr__(self):
        return str(self)

    def __getattr__(self, item):
        cls_name, _ = self.ws._try_get_module(self._name)
        try:
            cls = self.ws._app.load_module(cls_name)
        except KeyError:
            raise KeyError('definition of module %s not found', cls_name)
        return getattr(cls, item)


class Module:
    """Interface for configurable modules.

    Each module class should have an ``configure`` class method to define
    model arguments along with their types, default values, etc.
    """

    submodules = []

    @property
    def ws(self):
        if self._ws is not None:
            return self._ws
        raise NoWorkspaceError('should be run in a workspace')

    @ws.setter
    def ws(self, ws):
        self._ws = ws

    @classproperty
    def help(cls):
        return 'module ' + cls.__name__

    @classmethod
    def _add_arguments(cls, parser: argparse.ArgumentParser):
        for base_cls in reversed(cls.__mro__):
            if hasattr(base_cls, 'add_arguments'):
                base_cls.add_arguments(parser)
        for submodule in cls.submodules:
            parser.add_argument('-' + submodule, default=submodule,
                                help='submodule ' + submodule)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        """Add arguments to an argparse subparser."""
        pass

    def __init__(self, **kwargs):
        """
        Args:
            config (dict): module configuration
        """
        self.config = Configuration(kwargs)
        self._ws = None

    def __str__(self):
        return self.__class__.__name__ + '(' + str(self.config) + ')'

    def __repr__(self):
        return str(self)


def _mkdir(p, is_dir=False):
    if is_dir:
        if not p.exists():
            p.mkdir(parents=True)
    else:
        if not p.parent.exists():
            p.parent.mkdir(parents=True)


__all__ = ['Workspace', 'Run', 'Accumulator', 'Range', 'Module', 'Builder']
