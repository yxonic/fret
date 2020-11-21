import functools
import inspect as ins

from .util import _dict as dict, classproperty, Configuration

configurables = dict()
commands = dict()


class Module:
    """Interface for configurable modules.

    Each module class should have an ``add_arguments`` class method to define
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
    def help(cls):  # pylint: disable=no-self-argument
        return 'module ' + cls.__name__  # pylint: disable=no-member

    def __init__(self, **kwargs):
        """
        Args:
            config (dict): module configuration
        """
        self.config = Configuration(kwargs)
        self._ws = None

    def __str__(self):
        return self.__class__.__name__ + '(' + str(self.config) + ')'


class argspec:
    """In control of the behavior of commands. Replicates arguments for
    :meth:`argparse.ArgumentParser.add_argument`."""

    __slots__ = ['_args', '_kwargs', '_params']

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._params = None

    def default(self):
        return self._kwargs.get('default')

    def spec(self):
        return self._args, self._kwargs

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


class funcspec:
    """Utility to generate argument specification from function signature."""

    __slots__ = ['pos', 'kw', 'kw_only', 'varkw']

    def __init__(self, f):
        spec = ins.getfullargspec(f)
        self.varkw = spec.varkw
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
                defaults.update(dict([(self.kw[i][0], args[i - n_other])
                                      for i in range(n_other)]))
                args = args[:-n_other]
        defaults.update(dict([(k, v.default()) for k, v in self.kw]))
        defaults.update(kwargs)
        cfg = list(zip(self.pos, args)) + list(defaults.items())
        return args, defaults, cfg


def configurable(wraps=None, submodules=None, build_subs=True, states=None):
    """Class decorator that registers configurable module under current app.

    Args:
        wraps (class or None) : object to be decorated; could be given later
        submodules (list) : submodules of this module
        build_subs (bool) : whether submodules are built before building this
                            module (default: ``True``)
        states (list) : members that would appear in state_dict
    """
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

        def new_init(sf, *args, **kwargs):
            # get config from signature
            args, kwargs, cfg = spec.get_call_args(sf, *args, **kwargs)
            if not hasattr(sf, 'config'):
                d = dict(cfg[1:])  # remove self
                Module.__init__(sf, **d)
            orig_init(*args, **kwargs)

        # inherit Module methods
        for k, v in Module.__dict__.items():
            if k != '__dict__' and k not in cls.__dict__:
                setattr(cls, k, v)
        setattr(cls, '__init__', new_init)
        setattr(cls, 'state_dict', state_dict)
        setattr(cls, 'load_state_dict', load_state_dict)
        setattr(cls, '_build_subs', build_subs)
        setattr(cls, '__funcspec__', spec)
        configurables[cls.__name__] = cls
        return cls

    if wraps is None:
        return wrapper
    else:
        return wrapper(wraps)


def command(wraps=None, help=None, description=None):
    """Function decorator that would turn a function into a fret command."""
    def wrapper(f):
        if not ins.isfunction(f):
            raise TypeError('only function can form command')
        name = f.__name__
        spec = funcspec(f)
        ftype = 'function'
        if spec.pos and (spec.pos[0] == 'ws' or spec.pos[0] == 'self'):
            static = False
            if spec.pos[0] == 'self':
                ftype = 'method'
        else:
            static = True

        @functools.wraps(f)
        def new_f(*args, **kwargs):
            args, kwargs, cfg = spec.get_call_args(*args, **kwargs)
            if hasattr(new_f, 'global_config'):
                d = new_f.global_config.copy()
                d.update(dict(cfg[int(not static):]))
                cfg = d
            else:
                d = dict(cfg[int(not static):])
            cfg = cfg[int(not static):]
            new_f.config = Configuration(cfg)
            return f(*args, **kwargs)

        setattr(new_f, '__funcspec__', spec)
        setattr(new_f, '__static__', static)
        setattr(new_f, '__functype__', ftype)
        if help is not None:
            setattr(new_f, '__help__', help)
        if description is not None:
            setattr(new_f, '__desc__', description)

        commands[name] = new_f
        return new_f

    if wraps is None:
        return wrapper
    else:
        return wrapper(wraps)


class NotConfiguredError(Exception):
    pass


class NoWorkspaceError(Exception):
    pass


class NoAppError(Exception):
    pass
