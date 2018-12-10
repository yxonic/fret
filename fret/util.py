import inspect as ins
import re


def wrap_parser(namespace, parser):  # pragma: no cover
    """Wraps an argument parser, putting all following options under a
    namespace. """
    robj = re.compile(r'^(-+)')

    class _Wrapper:
        def __init__(self, _parser):
            self.parser = _parser

        def add_argument(self, *args, **kwargs):
            args = [robj.sub(r'\1' + namespace + '.', s) for s in args]
            self.parser.add_argument(*args, **kwargs)

    return _Wrapper(parser)


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


def sub_class_checker(cls):
    def rv(obj):
        if ins.isclass(obj) and not ins.isabstract(obj) \
                and issubclass(obj, cls):
            return True
        else:
            return False

    return rv
