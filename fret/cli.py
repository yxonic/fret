import shutil

from .common import command, argspec
from .workspace import Workspace
from .util import collect


@command(help='fork workspace, possibly with modifications')
def fork(ws, path, mods=([], 'modifications (in format: NAME.ARG=VAL)')):
    """Command ``fork``,

    Fork from existing workspace and change some of the arguments.

    Example:
        .. code-block:: bash

            $ fret fork ws/test main.foo=6
            In [ws/test]: as in [ws/_default], with modification(s): main.foo=6
    """
    conf = ws.config_dict()
    for mod in mods:
        k, v = mod.split('=')
        d = conf
        if '.' not in k:
            k = 'main.' + k
        fields = k.split('.')
        try:
            for field in fields[:-1]:
                d = d[field]
            d[fields[-1]]  # try get last field
        except KeyError as e:
            print('{}: no such key to modify'.format(e.args[0]))
            return
        d[fields[-1]] = v

    ws_ = Workspace(path, config_dict=conf)
    ws_.write()


@command(help='clean workspace')
def clean(ws,
          config=(False, 'remove workspace configuration'),
          log=(False, 'clear workspace logs'),
          snapshot=(False, 'clear snapshots'),
          everything=argspec(
              '-a', action='store_true',
              help='clear everything except for configuration'
          ),
          all=argspec('--all', action='store_true',
                      help='clean the entire workspace')):
    """Command ``clean``.

    Remove all snapshots in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    if all:
        shutil.rmtree(str(ws))
    else:
        if (not config and not log) or snapshot or everything:
            # fret clean or fret clean -s ... or fret clean -a ...
            shutil.rmtree(str(ws.snapshot()))

        if log or everything:
            shutil.rmtree(str(ws.log()))

        if config:
            try:
                (ws.path / 'config.toml').unlink()
            except FileNotFoundError:
                pass


def _selection_to_order(selection):
    order = []
    lo = 0
    while True:
        # noinspection PyUnresolvedReferences
        try:
            hi = selection.index('_', lo)
        except ValueError:
            # no _ left
            order.append(selection[lo:])
            break
        order.append(selection[lo:hi])
        lo = hi + 1
    if len(order) == 1:
        order = order[0]
    return order


@command(help='collect results and summarize')
def summarize(
    rows=argspec(
        help='row names',
        nargs='+', default=None
    ),
    columns=argspec(
        help='column names',
        nargs='*', default=None
    ),
    row_selection=argspec(
        help='selection of row headers, different headers separated '
             'by _ (eg: -rs H1 H2 _ h1 h2)',
        nargs='+', default=None
    ),
    column_selection=argspec(
        help='selection of column headers, different headers '
             'separated by _ (eg: -rs C1 C2 _ c1 c2)',
        nargs='+', default=None
    ),
    scheme=('best', 'output scheme',
            ['best', 'mean', 'mean_with_error']),
    topk=(-1, 'if >0, best k results will be taken into account'),
    format=(None, 'float point format spec (eg: .4f)'),
    output=(None, 'output format', ['html', 'latex']),
    glob=('ws/**', 'workspace pattern'),
    last=(False, 'only retrieve last record in each result directory')
):
    """Command ``summarize``.

    Summarize all results recorded by ``ws.record``.
    """
    summarizer = collect(glob, last)
    if len(summarizer) == 0:
        raise ValueError('no results found')

    row_order = row_selection and _selection_to_order(row_selection)
    column_order = column_selection and _selection_to_order(column_selection)

    schemes = []
    if scheme == 'mean_with_error':
        schemes.append(lambda x: (x.mean(), x.std()))
        spec = ':' + format if format else ''
        fmt = r'{%s}$\pm${%s}' % (spec, spec) if output == 'latex' \
            else '{%s}±{%s}' % (spec, spec)
        schemes.append(lambda x: fmt.format(*x))
    else:
        schemes.append(scheme)
        if format:
            fmt = '{:%s}' % format
            schemes.append(lambda x: fmt.format(x))
    df = summarizer.summarize(rows, columns, row_order, column_order,
                              scheme=schemes, topk=topk)
    if output == 'latex':
        return df.to_latex(escape=False)
    if output == 'html':
        return df.to_html(escape=False)
    return df


def main(args=None):
    pass


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
