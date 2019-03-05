import functools
import inspect
import itertools
import logging
import signal
from collections import OrderedDict


class Configuration:
    __slots__ = '_config'

    """Easy to construct, use and read configuration class."""
    def __init__(self, *args, **kwargs):
        self._config = OrderedDict(*args, **kwargs)

    def _keys(self):
        return self._config.keys()

    def _values(self):
        return self._config.values()

    def _items(self):
        return self._config.items()

    def _get(self, key):
        return self._config.get(key)

    def __getitem__(self, key):
        return self._config[key]

    def __getattr__(self, key):
        v = self._config[key]
        if isinstance(v, dict):
            return Configuration(v)
        else:
            return v

    def __contains__(self, key):
        return key in self._config

    def __eq__(self, other):
        return dict(self._config) == dict(other._config)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

    def __str__(self):
        return ', '.join(k + '=' + repr(v)
                         for k, v in self._config.items()
                         if not k.startswith('_'))

    def __repr__(self):
        return ', '.join(k + '=' + repr(v) for k, v in self._config.items())

    def _dict(self):
        return self._config


class classproperty(object):
    __slots__ = '_f'

    def __init__(self, f):
        self._f = f

    def __get__(self, obj, owner):
        return self._f(owner)


def colored(fmt, fg=None, bg=None, style=None):
    """
    Return colored string.

    List of colours (for fg and bg):
        k   black
        r   red
        g   green
        y   yellow
        b   blue
        m   magenta
        c   cyan
        w   white

    List of styles:
        b   bold
        i   italic
        u   underline
        s   strike through
        x   blinking
        r   reverse
        y   fast blinking
        f   faint
        h   hide

    Args:
        fmt (str): string to be colored
        fg (str): foreground color
        bg (str): background color
        style (str): text style
    """

    colcode = {
        'k': 0,  # black
        'r': 1,  # red
        'g': 2,  # green
        'y': 3,  # yellow
        'b': 4,  # blue
        'm': 5,  # magenta
        'c': 6,  # cyan
        'w': 7   # white
    }

    fmtcode = {
        'b': 1,  # bold
        'f': 2,  # faint
        'i': 3,  # italic
        'u': 4,  # underline
        'x': 5,  # blinking
        'y': 6,  # fast blinking
        'r': 7,  # reverse
        'h': 8,  # hide
        's': 9,  # strike through
    }

    # properties
    props = []
    if isinstance(style, str):
        props = [fmtcode[s] for s in style]
    if isinstance(fg, str):
        props.append(30 + colcode[fg])
    if isinstance(bg, str):
        props.append(40 + colcode[bg])

    # display
    props = ';'.join([str(x) for x in props])
    if props:
        return '\x1b[%sm%s\x1b[0m' % (props, fmt)
    else:
        return fmt


def optional(default, position=1):
    def wrapper(f):
        spec = inspect.getfullargspec(f)
        expected_len = len(spec.args)

        @functools.wraps(f)
        def new_f(*args, **kwargs):
            if len(args) == expected_len - 1:
                args = args[:position] + (default,) + args[position:]
            return f(*args, **kwargs)

        return new_f
    return wrapper


def stateful(*states):
    _cls = None
    if len(states) == 1 and inspect.isclass(states[0]):
        _cls = states[0]
        states = _cls.__slots__

    def wrapper(cls):
        def state_dict(self):
            return {s: getattr(self, s) for s in states}

        def load_state_dict(self, state):
            for s in states:
                setattr(self, s, state[s])

        cls.state_dict = state_dict
        cls.load_state_dict = load_state_dict
        return cls

    if _cls is not None:
        return wrapper(_cls)
    else:
        return wrapper


_sigint_handler = signal.getsignal(signal.SIGINT)


def nonbreak(f=None):  # pragma: no cover
    if f is not None:
        it = iter(f)
    else:
        it = itertools.count()
    signal_received = ()

    def handler(sig, frame):
        nonlocal signal_received
        signal_received = (sig, frame)
        logging.warning('SIGINT received. Delaying KeyboardInterrupt.')

    while True:
        try:
            signal.signal(signal.SIGINT, handler)
            yield next(it)
            signal.signal(signal.SIGINT, _sigint_handler)
            if signal_received:
                _sigint_handler(signal_received)
        except StopIteration:
            break
