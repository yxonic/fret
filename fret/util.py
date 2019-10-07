import functools
import importlib
import inspect
import itertools
import json
import logging
import math
import os
import queue
import random
import signal
import sys
import threading
import glob as _glob
from datetime import datetime
from collections.abc import Iterable

if sys.implementation.name == 'cpython':
    _LOWEST_VERSION = (3, 6)
else:
    _LOWEST_VERSION = (3, 7)
if sys.version_info >= _LOWEST_VERSION:
    _dict = dict
else:
    from collections import OrderedDict
    _dict = OrderedDict

start_time = datetime.now().strftime("%Y%m%d%H%M%S")


class Configuration:
    """Easy to construct, use and read configuration class."""
    __slots__ = ['_config']

    def __init__(self, *args, **kwargs):
        self._config = _dict(*args, **kwargs)

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
        if key == '__setstate__':
            raise AttributeError(key)
        if key not in self._config:
            raise AttributeError(key)
        v = self._config[key]
        if isinstance(v, dict):
            return Configuration(v)
        else:
            return v

    def __contains__(self, key):
        return key in self._config

    def __eq__(self, other):
        if isinstance(other, Configuration):
            # pylint: disable=protected-access
            return dict(self._config) == dict(other._config)
        return dict(self._config) == other

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
    """Class property decorator."""
    __slots__ = '_f'

    def __init__(self, f):
        self._f = f

    def __get__(self, obj, owner):
        return self._f(owner)


def colored(fmt, fg=None, bg=None, style=None):
    """
    Return colored string.

    List of colours (for fg and bg):
        - k:   black
        - r:   red
        - g:   green
        - y:   yellow
        - b:   blue
        - m:   magenta
        - c:   cyan
        - w:   white

    List of styles:
        - b:   bold
        - i:   italic
        - u:   underline
        - s:   strike through
        - x:   blinking
        - r:   reverse
        - y:   fast blinking
        - f:   faint
        - h:   hide

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


def _pairwise(l):
    i = 0
    while i < len(l):
        yield l[i], l[i + 1]
        i += 2


def overload(*rules):
    """Decorator for defining function overloads."""
    if len(rules) % 2 != 0:
        raise ValueError("every guard must have an action.")

    def wrapper(f):
        @functools.wraps(f)
        def new_f(*args, **kwargs):
            for guard, action in _pairwise(rules):
                if match(args, guard):
                    if action is ...:
                        break
                    args = action(*args)
                    break
            else:
                raise ValueError('argument not match any overloads')
            return f(*args, **kwargs)
        return new_f
    return wrapper


def match(args, rule):
    """Simple pattern matching."""
    if rule is ...:
        return True
    if not isinstance(rule, tuple) and not isinstance(rule, list):
        if isinstance(rule, type):
            return all(isinstance(x, rule) for x in args)
        else:
            return all(x == rule for x in args)
    if len(args) != len(rule):
        return False
    return all(r is ... or
               (isinstance(r, type) and isinstance(x, r)) or
               (not isinstance(r, type) and x == r)
               for x, r in zip(args, rule))


def stateful(*states):
    """Decorator for building stateful classes."""
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


def nonbreak(f=None):
    """Make sure a loop is not interrupted in between an iteration."""
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


@stateful('batch_size', 'index', 'pos')
class Iterator:
    """Iterator on data and labels, with states for save and restore."""

    def __init__(self, data, *label, prefetch=False,
                 length=None, batch_size=None, shuffle=True,
                 full_shuffle=False):
        self.data = data
        self.label = label
        self.prefetch = prefetch
        self.batch_size = batch_size
        self.queue = queue.Queue(maxsize=8)
        self.length = length if length is not None else len(data)

        assert all(self.length == len(lab) for lab in label), \
            'data and label must have same lengths'

        self.index = list(range(len(self)))
        self.full_index = None
        if shuffle:
            random.shuffle(self.index)
        if full_shuffle:
            self.full_index = list(range(self.length))
            random.shuffle(self.full_index)

        self.thread = None
        self.pos = 0

    def __len__(self):
        if self.batch_size is None:
            return self.length
        return math.ceil(self.length / self.batch_size)

    def __iter__(self):
        return self

    def __next__(self):
        if self.thread is None and self.prefetch:
            self.thread = threading.Thread(target=self.produce, daemon=True)
            self.thread.start()

        if self.pos >= len(self.index):
            raise StopIteration

        if not self.prefetch:
            self.produce(False)
        item = self.queue.get()
        if isinstance(item, Exception):
            raise item
        else:
            self.pos += 1
            return item

    def produce(self, daemon=True):
        if self.batch_size is None:
            # no batch, direct indexing
            try:
                for i in range(self.pos, self.length):
                    data = self.data[i]
                    label = [label[i] for label in self.label]
                    if label:
                        self.queue.put([data] + label)
                    else:
                        self.queue.put(data)

                    if not daemon:
                        return

            except Exception as e:
                if daemon:
                    self.queue.put(e)
                    return
                else:
                    raise

        if self.full_index:
            for i in range(self.pos, len(self)):
                try:
                    bs = self.batch_size
                    inds = self.full_index[i * bs:(i + 1) * bs]

                    if callable(self.data):
                        data_batch = [self.data(i, i + 1) for i in inds]
                    else:
                        data_batch = [self.data[i:i + 1] for i in inds]

                    label_batch = [[label(i, i + 1) for i in inds]
                                   if callable(label)
                                   else [label[i:i+1] for i in inds]
                                   for label in self.label]

                    if label_batch:
                        self.queue.put([data_batch] + label_batch)
                    else:
                        self.queue.put(data_batch)

                    if not daemon:
                        return

                except Exception as e:
                    if daemon:
                        self.queue.put(e)
                        return
                    else:
                        raise

        else:
            for i in range(self.pos, len(self)):
                try:
                    index = self.index[i]

                    bs = self.batch_size

                    if callable(self.data):
                        data_batch = self.data(index * bs, (index + 1) * bs)
                    else:
                        data_batch = self.data[index * bs:(index + 1) * bs]

                    label_batch = [label(index * bs, (index + 1) * bs)
                                   if callable(label)
                                   else label[index * bs:(index + 1) * bs]
                                   for label in self.label]

                    if label_batch:
                        self.queue.put([data_batch] + label_batch)
                    else:
                        self.queue.put(data_batch)

                    if not daemon:
                        return

                except Exception as e:
                    if daemon:
                        self.queue.put(e)
                        return
                    else:
                        raise


def collect(glob, last=False):
    summarizer = Summarizer()

    last_dirname = None
    for file in sorted(_glob.glob(glob + '/*.json-lines', recursive=True),
                       reverse=True):
        if last_dirname != os.path.dirname(file):
            last_dirname = os.path.dirname(file)
        elif last:
            continue
        for line in open(file):
            summarizer.add(**json.loads(line))

    return summarizer


class Summarizer:
    def __init__(self, data=None):
        self.data = data or []
        self.is_des = {}

    def __len__(self):
        return len(self.data)

    def add(self, value, metrics, **kwargs):
        _metrics = metrics.rstrip('+-')
        self.is_des[_metrics] = metrics.endswith('-')
        data = {'metrics': _metrics, 'value': value}
        data.update(kwargs)
        self.data.append(data)

    def df(self):
        try:
            pd = importlib.import_module('pandas')
        except ImportError:
            raise ImportError('pandas needed for result summarization')
        return pd.DataFrame(self.data)

    def summarize(self, rows=None, columns=None, row_order=None,
                  column_order=None, scheme='best', topk=-1, filter=None):
        df = self.df()
        pd = importlib.import_module('pandas')
        if filter is not None:
            df = filter(df)
        if rows is None and columns is None:
            columns = ['metrics']
        if rows is None or columns is None:
            current = set(rows or columns)
            current.add('value')
            groups = [c for c in df.columns if c not in current]
            if rows is None:
                rows = groups
            else:
                columns = groups
        groups = rows + columns
        df = df.groupby(groups)['value']
        ind = groups.index('metrics')

        if isinstance(scheme, str) or not isinstance(scheme, Iterable):
            scheme = [scheme]

        def f(x):
            if topk > 0:
                x = x.sort_values(
                    ascending=self.is_des.get(x.name[ind])
                )[:topk]
            for s in scheme:
                if s == 'best':
                    x = x.min() if self.is_des.get(x.name[ind]) else x.max()
                elif s == 'mean':
                    x = x.mean()
                elif callable(s):
                    x = s(x)
                else:
                    raise ValueError('scheme not supported')
            return x

        df = df.apply(f)
        df = df.unstack(columns)
        if row_order is not None:
            if isinstance(row_order[0], list):
                df = df.reindex(
                    pd.MultiIndex.from_product(row_order,
                                               names=df.rows.names),
                    axis=0
                )
            else:
                df = df.reindex(row_order, axis=0)
        if column_order is not None:
            if isinstance(column_order[0], list):
                df = df.reindex(
                    pd.MultiIndex.from_product(column_order,
                                               names=df.columns.names),
                    axis=1
                )
            else:
                df = df.reindex(column_order, axis=1)
        return df
