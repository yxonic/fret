import abc
import argparse
import importlib
import inspect as ins
import logging
import pathlib
import sys
import toml

from collections import namedtuple
from functools import lru_cache
from operator import itemgetter

from . import util


class NotConfiguredError(Exception):
    pass


class ParseError(Exception):
    pass


@lru_cache(maxsize=1)
def get_app():
    sys.path.append('.')
    config = toml.load(open('fret.toml'))
    models = importlib.import_module(config['appname'] + '.module')
    command = importlib.import_module(config['appname'] + '.command')
    return {'module': models, 'command': command}


class Module(abc.ABC):
    """Interface for configurable modules.

    Each module class should have an ``configure`` class method to define
    model arguments along with their types, default values, etc.
    """

    submodules = []

    @util.classproperty
    def help(cls):
        return 'module ' + cls.__name__

    @classmethod
    @abc.abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        """Add arguments to an argparse subparser."""
        raise NotImplementedError

    @classmethod
    def parse(cls, args):
        """Parse command-line options and build module."""

        class _ArgumentParser(argparse.ArgumentParser):
            def error(self, message):
                raise ParseError(message)

        parser = _ArgumentParser(prog='', add_help=False)
        cls.add_arguments(parser)
        args = parser.parse_args(args)
        config = dict(args._get_kwargs())
        return cls(**config)

    def __init__(self, **kwargs):
        """
        Args:
            config (namedtuple): module configuration
        """
        keys, values = zip(*sorted(list(kwargs.items()), key=itemgetter(0)))
        config = namedtuple(self.__class__.__name__, keys)(*values)
        self.config = config

    def __str__(self):
        return str(self.config)

    def __repr__(self):
        return str(self)


def configurable(cls):
    orig_init = cls.__init__
    spec = ins.getfullargspec(orig_init)
    n_config = len(spec.defaults)
    submodules = spec.args[1:] if n_config == 0 else spec.args[1:-n_config]
    config = dict() if n_config == 0 else \
        {k: v for k, v in zip(spec.args[-n_config:], spec.defaults)}

    def new_init(self, *args, **kwargs):
        Module.__init__(**ins.getcallargs(
            orig_init, self, *args, **kwargs))
        cls.__init__(self, *args, **kwargs)

    @classmethod
    def add_arguments(cls, parser):
        for k, v in config.items():
            if isinstance(v, tuple):
                v = {x: y for x, y in v}
                value = v.get('default') or None
                dtype = v.get('type') or None
                if dtype is None and value is not None:
                    dtype = type(value)
                help = v.get('help') or ''
                required = v.get('required') or False
            else:
                value = v
                dtype = type(v)
                help = ''
                required = False

            if dtype is None:
                parser.add_argument('-' + k, help=help, required=required)
            elif value is None:
                parser.add_argument('-' + k, help=help,
                                    type=dtype, required=required)
            else:
                parser.add_argument('-' + k, default=value, required=required,
                                    type=dtype, help=help)

    new_cls = type(cls.__name__, (cls, Module),
                   dict(__init__=new_init,
                        add_arguments=add_arguments,
                        submodules=submodules))

    return new_cls


class Workspace:
    """Workspace utilities. One can save/load configurations, build models
    with specific configuration, save snapshots, open results, etc., using
    workspace objects."""

    def __init__(self, path: str):
        self._path = pathlib.Path(path)
        self._log_path = self._path / 'log'
        self._snapshot_path = self._path / 'snapshot'
        self._result_path = self._path / 'result'
        self._config_path = self._path / 'config.toml'
        self._modules = None

    def load(self):
        """Load configuration."""
        self._modules = {}
        config = toml.load(self.config_path.open())
        for name, cfg in config.items():
            cls = self.__class__._get_module_cls(cfg['module'])
            del cfg['module']
            self.add_module(name, cls, cfg)

    def save(self):
        """Save configuration."""
        f = self.config_path.open('w')
        cfg = {name: dict({'module': cls.__name__}, **cfg)
               for name, (cls, cfg) in self._modules.items()}
        toml.dump(cfg, f)
        f.close()

    @staticmethod
    def _get_module_cls(name):
        return getattr(get_app()['module'], name)

    @property
    def path(self):
        if not self._path.exists():
            self._path.mkdir(parents=True)
        return self._path

    @property
    def result_path(self):
        if not self._result_path.exists():
            self._result_path.mkdir(parents=True)
        return self._result_path

    @property
    def snapshot_path(self):
        if not self._snapshot_path.exists():
            self._snapshot_path.mkdir(parents=True)
        return self._snapshot_path

    @property
    def log_path(self):
        if not self._log_path.exists():
            self._log_path.mkdir(parents=True)
        return self._log_path

    @property
    def config_path(self):
        if not self._config_path.exists():
            self._config_path.open('w').close()
        return self._config_path

    def add_module(self, name, module, config):
        self._modules[name] = (module, config)

    def get_module(self, name='main'):
        if self._modules is None:
            self.load()
        if name in self._modules:
            return self._modules[name]
        else:
            raise NotConfiguredError('module %s not configured' % name)

    def build_module(self, name='main'):
        """Build module according to the configurations in current
        workspace."""
        cls, cfg = self.get_module(name)
        for sub in cls.submodules:
            if sub in cfg:
                cfg[sub] = self.build_module(sub)
        return cls(**cfg)

    def logger(self, name: str):
        """Get a logger that logs to a file.

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
            str(self.log_path / (name + '.log')))
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        return logger

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return 'Workspace(path=' + str(self.path) + ')'


class Command(abc.ABC):
    """Command interface."""

    @util.classproperty
    def help(cls):
        return 'command ' + cls.__name__.lower()

    def __init__(self, parser):
        self.parser = parser

    def _run(self, args):
        ws = Workspace(args.workspace)
        cmd = args.command
        del args.command, args.func, args.workspace
        # noinspection PyProtectedMember
        args = {name: value for (name, value) in args._get_kwargs()}
        args = namedtuple(cmd.capitalize(), args.keys())(*args.values())
        return self.run(ws, args)

    @abc.abstractmethod
    def run(self, ws, args):
        raise NotImplementedError
