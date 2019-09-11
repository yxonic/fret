import abc
import argparse
import collections
import functools
import importlib
import inspect as ins
import logging
import os
import pathlib
import shutil
import sys

import toml

from .exceptions import NotConfiguredError
from .common import Module, Workspace
# pylint: disable=redefined-builtin
# noinspection PyShadowingBuiltins
from .util import classproperty, Configuration, colored, _dict as dict


class Command(abc.ABC):
    """Command interface."""
    __slots__ = []

    @classproperty
    def help(cls):  # pylint: disable=no-self-argument
        # pylint: disable=no-member
        return 'command ' + cls.__name__.lower()

    def _run(self, args):
        # pylint: disable=protected-access
        ws = get_app().workspace(args.workspace)
        del args.command, args.func, args.workspace
        args = {name: value for (name, value) in args._get_kwargs()}
        args = Configuration(args)
        return self.run(ws, args)

    @abc.abstractmethod
    def run(self, ws, args):
        raise NotImplementedError


class config(Command):
    """Command ``config``,

    Configure a module and its parameters for a workspace.

    Example:
        .. code-block:: bash

            $ fret config Simple -foo=5
            In [ws/_default]: configured "main" as "Simple" with: foo=5
    """

    help = 'configure module for workspace'

    def __init__(self, app, parser):
        # pylint: disable=protected-access
        parser.add_argument('name', default='main', nargs='?',
                            help='module name')
        if sys.version_info < (3, 7):
            subs = parser.add_subparsers(title='modules available',
                                         dest='module')
        else:
            subs = parser.add_subparsers(title='modules available',
                                         dest='module', required=False)
        group_options = collections.defaultdict(set)
        try:
            _modules = app._modules
        except ImportError:
            _modules = dict()

        for module, module_cls in _modules.items():
            _parser_formatter = argparse.ArgumentDefaultsHelpFormatter
            sub = subs.add_parser(module, help=module_cls.help,
                                  formatter_class=_parser_formatter)
            group = sub.add_argument_group('config')
            module_cls._add_arguments(group)
            for action in group._group_actions:
                group_options[module].add(action.dest)

            def save(args):
                with get_app().workspace(args.workspace) as ws:
                    m = args.module
                    cfg = [(name, value)
                           for (name, value) in args._get_kwargs()
                           if name in group_options[m]]
                    cfg = Configuration(cfg)
                    msg = '[%s] configured "%s" as "%s"' % \
                        (ws, args.name, m)
                    if cfg._config:
                        msg += ' with: ' + str(cfg)
                    print(msg, file=sys.stderr)
                    ws.register(args.name, get_app().load_module(m),
                                **cfg._dict())

            sub.set_defaults(func=save)

    def run(self, ws, args):
        cfg = ws.config_path
        if cfg.exists():
            cfg = cfg.open().read().strip()
            return cfg
        else:
            raise NotConfiguredError('no configuration in this workspace')


class clean(Command):
    """Command ``clean``.

    Remove all checkpoints in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    help = 'clean workspace'

    def __init__(self, _, parser):
        parser.add_argument('--all', action='store_true',
                            help='clean the entire workspace')
        parser.add_argument('-c', dest='config', action='store_true',
                            help='remove workspace configuration')
        parser.add_argument('-l', dest='log', action='store_true',
                            help='clear workspace logs')
        parser.add_argument('-s', dest='snapshot', action='store_true',
                            help='clear snapshots')
        parser.add_argument('-a', action='store_true',
                            help='clear everything except for configuration')

    def run(self, ws, args):
        if args.all:
            shutil.rmtree(str(ws))
        else:
            if (not args.config and not args.log) or args.snapshot or args.a:
                # fret clean or fret clean -s ... or fret clean -a ...
                shutil.rmtree(str(ws.snapshot()))

            if args.log or args.a:
                shutil.rmtree(str(ws.log()))

            if args.config:
                try:
                    (ws.path / 'config.toml').unlink()
                except FileNotFoundError:
                    pass


class App:
    """Application object. In charge of locating suitable app, importing
    modules, and run commands."""

    __slots__ = ['_root', '_config', '_commands', '_modules', '_cwd', '_imp']

    def __init__(self, path=None):
        self._cwd = None
        if path is None:
            p = pathlib.Path().absolute()
            if p.joinpath('fret.toml').exists():
                path = str(p)
            else:
                while p != pathlib.Path(p.root):
                    if p.joinpath('fret.toml').exists():
                        path = str(p)
                        self._cwd = os.getcwd()
                        os.chdir(path)
                        break
                    p = p.parent
                else:
                    path = pathlib.Path().absolute()

        sys.path.insert(0, str(path))
        self._root = pathlib.Path(path)
        self._imp = None

        self._config = None
        self._commands = dict()
        self._modules = dict()

        if self._root.joinpath('fret.toml').exists():
            cfg = toml.load(self._root.joinpath('fret.toml').open())
        else:
            cfg = dict()
        self._config = Configuration(cfg)

    def import_modules(self):
        appname = os.environ.get('FRETAPP')
        if appname is not None:
            self._imp = importlib.import_module(appname)
        elif 'appname' in self._config:
            self._imp = importlib.import_module(self._config.appname)
        else:
            for appname in ['main', 'app']:
                try:
                    self._imp = importlib.import_module(appname)
                    break
                except ImportError as e:
                    if e.name != appname:
                        raise
            else:
                logging.warning('no app found')
        return self._imp

    def register_module(self, cls, name=None):
        if name is None:
            name = cls.__name__
        self._modules[name] = cls

    def register_command(self, cls, name=None):
        if name is None:
            name = cls.__name__
        self._commands[name] = cls

    def load_module(self, name):
        if self._config is None:
            self.load()
        return self._modules[name]

    @property
    def config(self):
        if self._config is None:
            self.load()
        return self._config

    @property
    def argument_style(self):
        style = self.config._get('argument_style')
        if style not in ['java', 'gnu']:
            return 'java'
        return style

    def workspace(self, path=None):
        if path is None:
            path = pathlib.Path(self._cwd).relative_to(self._root) if \
                self._cwd is not None else 'ws/_default'
        return Workspace(self, path)

    def __getattr__(self, key):
        return getattr(self.config, key)

    def main(self, args=None):
        self.import_modules()

        if self._modules:
            self.register_command(config)
            self.register_command(clean)

        main_parser = _ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog='fret')

        main_parser.add_argument('-q', action='store_true', help='quiet')
        main_parser.add_argument('-v', action='store_true', help='verbose')
        main_parser.add_argument('-w', '--workspace', help='workspace dir')

        _subparsers = main_parser.add_subparsers(title='supported commands',
                                                 dest='command')
        _subparsers.required = True

        subparsers = dict()
        for _cmd, _cls in self._commands.items():
            _sub = _subparsers.add_parser(
                _cmd, help=_cls.help,
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
            subparsers[_cmd] = _sub
            # pylint: disable=protected-access
            _sub.set_defaults(func=_cls(self, _sub)._run)

        args = main_parser.parse_args() if args is None \
            else main_parser.parse_args(args)

        # configure logger
        _logger = logging.getLogger()
        if args.q:
            _logger.setLevel(logging.WARNING)
        elif args.v:
            _logger.setLevel(logging.DEBUG)
        else:
            _logger.setLevel(logging.INFO)

        # remove logging related options
        del args.q
        del args.v

        logger = logging.getLogger(args.command)
        try:
            return args.func(args)
        except KeyboardInterrupt:
            # print traceback info to screen only
            import traceback
            sys.stderr.write(traceback.format_exc())
            logger.warning('cancelled by user')
        except NotConfiguredError as e:
            print('error:', e)
            subparsers['config'].print_usage()
            sys.exit(1)
        except Exception as e:  # pylint: disable=broad-except
            # print traceback info to screen only
            import traceback
            sys.stderr.write(traceback.format_exc())
            logger.error('exception occurred: %s: %s',
                         e.__class__.__name__, e)

    def configurable(self, wraps=None, submodules=None, states=None,
                     build_subs=True):
        def wrapper(cls):
            if not ins.isclass(cls):
                raise TypeError('only class can be configurable')
            orig_init = cls.__init__
            spec = funcspec(orig_init)

            if submodules is not None:
                if isinstance(submodules, str):
                    setattr(cls, 'submodules', submodules.split(','))
                else:
                    setattr(cls, 'submodules', submodules)

            orig_state_dict = getattr(cls, 'state_dict', lambda _: dict())
            orig_load_state_dict = getattr(cls, 'load_state_dict',
                                           lambda *_: None)

            def state_dict(sf, *args, **kwargs):
                if states:
                    d = {s: getattr(sf, s) for s in states}
                else:
                    d = dict()
                d.update(orig_state_dict(sf, *args, **kwargs))
                return d

            def load_state_dict(sf, state, *args, **kwargs):
                if states:
                    for s in states:
                        setattr(sf, s, state[s])
                        del state[s]
                orig_load_state_dict(sf, state, *args, **kwargs)

            @classmethod
            def add_arguments(_, parser):
                with ParserBuilder(parser, self.argument_style) as builder:
                    for name, opt in spec.kw:
                        builder.add_opt(name, opt)

            def new_init(sf, *args, **kwargs):
                # get config from signature
                args, kwargs, cfg = spec.get_call_args(sf, *args, **kwargs)
                if not hasattr(sf, 'config'):
                    global_config = self.config._get(cls.__name__)
                    if global_config:
                        d = global_config.copy()
                        d.update(dict(cfg[1:]))
                    else:
                        d = dict(cfg[1:])
                    Module.__init__(sf, **d)
                orig_init(*args, **kwargs)

            # inherit Module methods
            for k, v in Module.__dict__.items():
                if k != '__dict__' and k not in cls.__dict__:
                    setattr(cls, k, v)
            setattr(cls, '__init__', new_init)
            setattr(cls, 'add_arguments', add_arguments)
            setattr(cls, 'state_dict', state_dict)
            setattr(cls, 'load_state_dict', load_state_dict)
            setattr(cls, '_build_subs', build_subs)

            if not cls.__name__.startswith('_'):
                self.register_module(cls)
            return cls

        if wraps is None:
            return wrapper
        else:
            return wrapper(wraps)

    def command(self, f):
        if not ins.isfunction(f):
            raise TypeError('only function can form command')
        name = f.__name__
        spec = funcspec(f)
        if spec.pos and spec.pos[0] == 'ws':
            static = False
        else:
            static = True

        @functools.wraps(f)
        def new_f(*args, **kwargs):
            args, kwargs, cfg = spec.get_call_args(*args, **kwargs)
            global_config = self.config._get(name)
            if global_config:
                d = global_config.copy()
                d.update(dict(cfg[int(not static):]))
                cfg = d
            else:
                cfg = cfg[int(not static):]
            new_f.config = Configuration(cfg)
            return f(*args, **kwargs)

        argument_style = self.argument_style

        class _Command(Command):
            def __init__(self, _, parser):
                with ParserBuilder(parser, argument_style) as builder:
                    for arg in spec.pos[int(not static):]:
                        builder.add_opt(arg, argspec())
                    for k, v in spec.kw:
                        builder.add_opt(k, v)

            def run(self, ws, args):
                if static:
                    return new_f(**args._dict())
                else:
                    return new_f(ws, **args._dict())

        _Command.__name__ = name
        self.register_command(_Command)

        return new_f


class funcspec:
    """Utility to generate argument specification from function signature."""

    __slots__ = ['pos', 'kw', 'kw_only']

    def __init__(self, f):
        spec = ins.getfullargspec(f)
        if spec.defaults:
            self.kw_only = False
            n_config = len(spec.defaults)
            self.pos = spec.args[:-n_config]
            opts = [v if isinstance(v, argspec) else argspec.from_param(v)
                    for v in spec.defaults]
            self.kw = [] if n_config == 0 else \
                list(zip(spec.args[-n_config:], opts))
        else:
            self.kw_only = True
            self.pos = spec.args
            if spec.kwonlydefaults:
                self.kw = list(spec.kwonlydefaults.items())
            else:
                self.kw = []

    def get_call_args(self, *args, **kwargs):
        defaults = dict((k, v.default()) for k, v in self.kw)
        if not self.kw_only:
            if len(args) > len(self.pos):
                n_other = len(args) - len(self.pos)
                defaults.update(dict([(self.kw[i][0], args[i-n_other])
                                      for i in range(n_other)]))
                args = args[:-n_other]
        defaults.update(dict([(k, v.default()) for k, v in self.kw]))
        defaults.update(kwargs)
        cfg = list(zip(self.pos, args)) + list(defaults.items())
        return args, defaults, cfg


class argspec:
    """In control of the behavior of commands. Represents arguments for
    :meth:`argparse.ArgumentParser.add_argument`."""

    __slots__ = ['_args', '_kwargs', '_params']

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._params = None

    @classmethod
    def from_param(cls, param):
        kwargs = dict()

        if isinstance(param, tuple):
            assert len(param) == 2 or len(param) == 3, \
                'should be default, help[, choices]'
            kwargs['default'] = param[0]
            kwargs['help'] = param[1]
            if len(param) == 3:
                kwargs['choices'] = param[2]
        else:
            kwargs['default'] = param

        if isinstance(kwargs['default'], list):
            if kwargs['default']:
                kwargs['nargs'] = '+'
                kwargs['type'] = type(kwargs['default'][0])
            else:
                kwargs['nargs'] = '*'
        elif isinstance(kwargs['default'], bool):
            if kwargs['default']:
                kwargs['action'] = 'store_false'
            else:
                kwargs['action'] = 'store_true'
        elif kwargs['default'] is not None:
            kwargs['type'] = type(kwargs['default'])

        obj = cls(**kwargs)
        obj._params = param  # pylint: disable=protected-access
        return obj

    def default(self):
        return self._kwargs.get('default')

    def spec(self):
        return self._args, self._kwargs


class ParserBuilder:
    """Utility to generate CLI arguments in different styles."""
    def __init__(self, parser, style='java'):
        self._parser = parser
        self._style = style
        self._names = []
        self._spec = []

    def add_opt(self, name, spec):
        """Add option with specification.

        Args:
            name (str) : option name
            spec (argspec): argument specification"""

        if spec.default() is True:
            # change name for better bool support
            spec._kwargs['dest'] = name  # pylint: disable=protected-access
            name = 'no_' + name
        self._names.append(name)
        self._spec.append(spec)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        prefix = '-' if self._style == 'java' else '--'
        seen = set(self._names)
        for name, spec in zip(self._names, self._spec):
            if name.startswith('_'):
                continue
            args, kwargs = spec.spec()
            if not args:
                args = [prefix + name]
                short = ''.join(seg[0] for seg in name.split('_'))
                if short not in seen:
                    args.append('-' + short)
                    seen.add(short)
            else:
                kwargs['dest'] = name
            if 'help' not in kwargs:
                kwargs['help'] = 'parameter ' + name
            self._parser.add_argument(*args, **kwargs)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # customize error message
        self.print_usage(sys.stderr)
        err = colored('error:', 'r', style='b')
        self.exit(2, '%s %s\n' % (err, message))


_app = App()


def get_app():
    """Get current global app."""
    return _app


def set_global_app(app):
    """Set current global app."""
    global _app  # pylint: disable=global-statement
    _app = app


def workspace(path=None):
    """Build workspace within current app.

    Args:
        path (str) : workspace path (default: ``None``)
    """
    return get_app().workspace(path)


def configurable(wraps=None, submodules=None, build_subs=True, states=None):
    """Class decorator that registers configurable module under current app.

    Args:
        wraps (class or None) : object to be decorated; could be given later
        submodules (list) : submodules of this module
        build_subs (bool) : whether submodules are built before building this
                            module (default: ``True``)
        states (list) : members that would appear in state_dict
    """
    return get_app().configurable(wraps, submodules, states, build_subs)


def command(f):
    """Function decorator that would turn a function into a fret command."""
    return get_app().command(f)


__all__ = ['get_app', 'set_global_app', 'argspec', 'App',
           'workspace', 'configurable', 'command']
