import abc
import argparse
import importlib
import logging
import pathlib
import sys
import toml

from collections import namedtuple
from functools import lru_cache
from operator import itemgetter


class NotConfiguredError(Exception):
    pass


class ParseError(Exception):
    pass


@lru_cache(maxsize=1)
def get_app():
    sys.path.append('.')
    config = toml.load(open('.repe.toml'))
    models = importlib.import_module(config['appname'] + '.models')
    command = importlib.import_module(config['appname'] + '.command')
    return {'models': models, 'command': command}


class Model(abc.ABC):
    """Interface for model that can save/load parameters.

    Each model class should have an ``_add_argument`` class method to define
    model arguments along with their types, default values, etc.
    """

    @classmethod
    @abc.abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        """Add arguments to an argparse subparser."""
        raise NotImplementedError

    @classmethod
    def build(cls, **kwargs):
        """Build model. Parameters are specified by keyword arguments."""
        keys, values = zip(*sorted(list(kwargs.items()), key=itemgetter(0)))
        config = namedtuple(cls.__name__, keys)(*values)
        return cls(config)

    @classmethod
    def parse(cls, args):
        """Parse command-line options and build model."""

        class _ArgumentParser(argparse.ArgumentParser):
            def error(self, message):
                raise ParseError(message)

        parser = _ArgumentParser(prog='', add_help=False)
        cls.add_arguments(parser)
        args = parser.parse_args(args)
        # noinspection PyProtectedMember
        config = dict(args._get_kwargs())
        Model._unfold_config(config)
        return cls.build(**config)

    def __init__(self, config):
        """
        Args:
            config (namedtuple): model configuration
        """
        self.config = config

    def __str__(self):
        return str(self.config)

    @staticmethod
    def _unfold_config(cfg):
        for k, v in list(cfg.items()):
            if isinstance(v, dict):
                Model._unfold_config(v)
            if '.' not in k:
                continue
            d = cfg
            for sec in k.split('.')[:-1]:
                if sec in d:
                    d = d[sec]
                else:
                    d[sec] = {}
                    d = d[sec]
            d[k.split('.')[-1]] = v
            del cfg[k]


class Workspace:
    """Workspace utilities. One can save/load configurations, build models
    with specific configuration, save snapshots, open results, etc., using
    workspace objects."""

    def __init__(self, path: str, model=None, config=None):
        self._path = pathlib.Path(path)
        self._log_path = self._path / 'log'
        self._snapshot_path = self._path / 'snapshot'
        self._result_path = self._path / 'result'

        if model is None:
            self._model_cls = None
            self._config = None
            return

        if config is None:
            config = {}

        self._set_model(model, config)
        self._save()

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return 'Workspace(path=' + str(self.path) + ')'

    def _set_model(self, model, config):
        if isinstance(model, str):
            self._model_cls = Workspace._get_class(model)
        else:
            self._model_cls = model
        self._config = config

    @staticmethod
    def _get_class(name):
        return getattr(get_app()['models'], name)

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
    def model_name(self):
        return self.model_cls.__name__

    @property
    def model_cls(self):
        if self._model_cls is not None:
            return self._model_cls
        self._load()
        return self._model_cls

    @property
    def config(self):
        if self._config is not None:
            return self._config
        self._load()
        return self._config

    def setup_like(self, model: Model):
        """Configure workspace with configurations from a given model.

        Args:
            model (Model): model to be used
        """
        # noinspection PyProtectedMember
        self._set_model(model.__class__, model.config._asdict())

    def build_model(self):
        """Build model according to the configurations in current
        workspace."""
        return self.model_cls.build(**self.config)

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

    def _load(self):
        """Load configuration."""
        try:
            cfg = toml.load((self.path / 'config.toml').open())
            self._set_model(cfg['model_name'], cfg[cfg['model_name'].lower()])
        except (FileNotFoundError, KeyError):
            raise NotConfiguredError('config.toml doesn\'t exist or '
                                     'is incomplete')

    def _save(self):
        """Save configuration."""
        f = (self.path / 'config.toml').open('w')
        toml.dump({'model_name': self.model_name,
                   self.model_name.lower(): self.config}, f)
        f.close()


class Command(abc.ABC):
    """Command interface."""

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
