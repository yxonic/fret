import abc
import functools
import inspect as ins
import os
import pathlib
import sys
from collections import namedtuple

import toml

from .common import Module, Workspace
from .util import classproperty, Configuration


class arg:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class App:
    __slots__ = ['_root', '_config', '_commands', '_modules', '_cwd']

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
                    path = '.'
        sys.path.append(path)
        self._root = pathlib.Path(path)

        self._config = None
        self._commands = {}
        self._modules = {}

        if self._root.joinpath('fret.toml').exists():
            cfg = toml.load(self._root.joinpath('fret.toml').open())
        else:
            cfg = {}
        self._config = Configuration(cfg)

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

    def workspace(self, path=None):
        if path is None:
            path = pathlib.Path(self._cwd).relative_to(self._root) if \
                self._cwd is not None else 'ws/_default'
        return Workspace(self, path)

    def __getattr__(self, key):
        return getattr(self.config, key)

    def configurable(self, cls=None, submodules=None, states=None):
        def wrapper(cls):
            orig_init = cls.__init__
            positional, config, varkw = self._get_args(orig_init)
            if submodules is not None:
                setattr(cls, 'submodules', submodules)

            orig_state_dict = getattr(cls, 'state_dict', lambda _: {})
            orig_load_state_dict = getattr(cls, 'load_state_dict',
                                           lambda *_: None)

            def state_dict(self):
                if states:
                    d = {k: getattr(self, k) for k in states}
                else:
                    d = {}
                d.update(orig_state_dict(self))
                return d

            def load_state_dict(self, state):
                if states:
                    for k in states:
                        setattr(self, k, state[k])
                        del state[k]
                orig_load_state_dict(self, state)

            @classmethod
            def add_arguments(_, parser):
                self._add_arguments_by_kwargs(parser, config)

            def new_init(self, *args, **kwargs):
                # get config from signature
                allowed_args = set(positional[1:]) | set(x[0] for x in config)
                cfg = ins.getcallargs(orig_init, self, *args,
                                      **{k: v for k, v in kwargs.items()
                                         if k in allowed_args})
                del cfg['self']

                defaults = {k: v for k, v in config}
                for k in defaults:
                    v = cfg[k]
                    if v != defaults[k]:
                        continue
                    if isinstance(v, tuple):
                        if isinstance(v[0], tuple):
                            cfg[k] = {k_: v_ for k_, v_ in v}.get('default')
                        else:
                            cfg[k] = v[0]

                if not hasattr(self, 'config'):
                    _cfg = cfg.copy()
                    _cfg.update(kwargs)
                    Module.__init__(self, **_cfg)

                if varkw is None:
                    orig_init(self, **cfg)
                else:
                    cfg.update(kwargs)
                    orig_init(self, **cfg)

            # inherit Module methods
            for k, v in Module.__dict__.items():
                if k != '__dict__' and k not in cls.__dict__:
                    setattr(cls, k, v)
            setattr(cls, '__init__', new_init)
            setattr(cls, 'add_arguments', add_arguments)
            setattr(cls, 'state_dict', state_dict)
            setattr(cls, 'load_state_dict', load_state_dict)

            if not cls.__name__.startswith('_'):
                self.register_module(cls)
            return cls

        if cls is None:
            return wrapper
        else:
            return wrapper(cls)

    def command(self, f):
        _args, config, _ = self._get_args(f)

        @functools.wraps(f)
        def new_f(*args, **kwargs):
            cfg = {}
            for k, v in config:
                if isinstance(v, tuple):
                    cfg[k] = v[0]
                else:
                    cfg[k] = v
            cfg.update(kwargs)
            f_args = {k: v for k, v in zip(_args[1:], args[1:])}
            f_args.update(cfg)
            # TODO: make an util class for this
            new_f.args = namedtuple(f.__name__, f_args.keys())(
                *f_args.values())
            return f(*args, **cfg)

        class Cmd(Command):
            def __init__(self, parser):
                for arg in _args[1:]:
                    parser.add_argument('-' + arg)
                App._add_arguments_by_kwargs(parser, config)

            def run(self, ws, args):
                return new_f(ws, **args._asdict())

        Cmd.__name__ = f.name
        self.register_command(Cmd)

        return new_f

    @staticmethod
    def _get_args(f):
        spec = ins.getfullargspec(f)
        n_config = len(spec.defaults) if spec.defaults else 0
        args = spec.args if n_config == 0 else spec.args[:-n_config]
        kwargs = [] if n_config == 0 else \
            [(k, v) for k, v in zip(spec.args[-n_config:], spec.defaults)]
        return args, kwargs, spec.varkw

    @staticmethod
    def _add_arguments_by_kwargs(parser, config):
        abbrs = set()
        for k, v in config:
            # TODO: add arg style (java/gnu), better logic
            if isinstance(k, str) and k.startswith('_'):
                continue

            if '_' in k:
                parts = k.split('_')
                abbr = ''.join(p[:1] for p in parts)
            elif len(k) > 1:
                i = 1
                while k[:i] in abbrs and i < len(k):
                    i += 1
                abbr = k[:i]
            else:
                abbr = None

            if abbr is not None and abbr not in abbrs:
                abbrs.add(abbr)
                args = ['-' + k, '-' + abbr]
            else:
                args = ['-' + k]

            if isinstance(v, arg):
                if v.args:
                    parser.add_argument(*v.args, **v.kwargs)
                else:
                    parser.add_argument(*args, **v.kwargs)
                continue

            if isinstance(v, tuple):
                if len(v) > 0 and isinstance(v[0], tuple):
                    # kwargs for parser.add_argument
                    v = {x: y for x, y in v}
                else:
                    # just default value and help
                    if isinstance(v[0], bool):
                        if v[0]:
                            nv = {
                                'action': 'store_false',
                                'help': v[1],
                                'dest': k

                            }
                            args[0] = '-no' + k
                        else:
                            nv = {
                                'action': 'store_true',
                                'help': v[1]
                            }
                    elif isinstance(v[0], list):
                        nv = {
                            'default': v[0],
                            'help': v[1],
                            'nargs': '+' if v[0] else '*',
                            'type': type(v[0][0]) if v[0] else str
                        }
                    else:
                        nv = {
                            'default': v[0],
                            'type': type(v[0]),
                            'help': v[1]
                        } if v[0] is not None else {
                            'help': v[1]
                        }
                    if len(v) > 2:
                        nv['choices'] = v[2]
                    v = nv
                parser.add_argument(*args, **v)
            elif isinstance(v, bool):
                if v:
                    args[0] = '-no' + k
                    parser.add_argument(*args, action='store_false',
                                        help='argument %s' % k, dest=k)
                else:
                    parser.add_argument(*args, action='store_true',
                                        help='argument %s' % k)
            elif v is None:
                parser.add_argument(*args, help='argument %s' % k)
            else:
                parser.add_argument(*args, default=v, type=type(v),
                                    help='argument %s' % k)


class Command(abc.ABC):
    """Command interface."""
    __slots__ = []

    @classproperty
    def help(cls):
        return 'command ' + cls.__name__.lower()

    def _run(self, args):
        ws = app.workspace(args.workspace)
        cmd = args.command
        del args.command, args.func, args.workspace
        args = {name: value for (name, value) in args._get_kwargs()}
        args = namedtuple(cmd, args.keys())(*args.values())
        return self.run(ws, args)

    @abc.abstractmethod
    def run(self, ws, args):
        raise NotImplementedError


app = App()
workspace = app.workspace
configurable = app.configurable
command = app.command
