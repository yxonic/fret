from collections import OrderedDict

import toml


class Configuration:
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

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

    def __str__(self):
        return str(self._config)

    def __repr__(self):
        return str(self._config)

    def _toml(self):
        return toml.dumps(self._config)

    def _dict(self):
        return self._config


class classproperty(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


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
