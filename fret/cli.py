import argparse
import collections
import logging
import shutil
import sys
import os

from .common import command, argspec, commands, configurables, \
    NoAppError, NotConfiguredError
from .workspace import Workspace
from .util import collect, colored, ColoredFormatter, Configuration


def main(args=None):
    logger = logging.getLogger('fret')
    logger.setLevel(logging.INFO)
    formatter = ColoredFormatter(
        '%(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    try:
        from . import app
        argument_style = app.config._get('argument_style') or 'java'
    except NoAppError:
        app = None
        argument_style = 'java'

    main_parser = _ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        prog='fret',
        description='fret: Framework for Reproducible ExperimenTs')

    main_parser.add_argument('-q', action='store_true', help='quiet')
    main_parser.add_argument('-v', action='store_true', help='verbose')
    main_parser.add_argument('-w', '--workspace', help='workspace dir')

    if args is None:
        args = sys.argv[1:]

    with_help = False
    if '-h' in args:
        args.remove('-h')
        with_help = True
    if '--help' in args:
        args.remove('--help')
        with_help = True

    args, remaining = main_parser.parse_known_args(args)

    if with_help:
        remaining.append('-h')

    # configure logging level
    if args.q:
        logger.setLevel(logging.WARNING)
    elif args.v:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if args.workspace is None:
        cwd = os.getcwd()
        if app is not None and not os.path.samefile(cwd, app.root):
            ws_path = cwd
            os.chdir(app.root)
        else:
            ws_path = 'ws/_default'
    else:
        ws_path = args.workspace

    if os.path.exists(ws_path):
        ws = Workspace(ws_path)
    else:
        ws = None
    main = None

    subparsers = main_parser.add_subparsers(title='supported commands',
                                            dest='command')
    subparsers.required = True

    for cmd, f in commands.items():
        if f.__functype__ == 'method':
            if ws is None:
                continue
            cls_name = f.__wrapped__.__qualname__.split('.')[0]
            if main is None:
                try:
                    main = ws.build()
                except Exception:  # pylint: disable=broad-except
                    main = ''
            if cls_name != main.__class__.__name__:
                # not applicable
                continue

        sub = subparsers.add_parser(
            cmd,
            help=getattr(f, '__help__', 'command ' + cmd),
            description=getattr(f, '__desc__', None),
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        with ParserBuilder(sub, argument_style) as builder:
            for arg in f.__funcspec__.pos[int(not f.__static__):]:
                builder.add_opt(arg, argspec())
            for k, v in f.__funcspec__.kw:
                builder.add_opt(k, v)

        if f.__functype__ == 'method':
            sub.set_defaults(func=_default_func(f, main))
        else:
            sub.set_defaults(func=_default_func(f, Workspace(ws_path)))

    if app is not None:
        config_sub = subparsers.add_parser(
            'config', help='configure module for workspace',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        _add_config_sub(config_sub, argument_style)
        config_sub.set_defaults(func=_config_default_func)
    else:
        config_sub = None

    args = main_parser.parse_args(remaining)
    del args.q
    del args.v
    args.workspace = ws_path

    logger = logging.getLogger('fret.' + args.command)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        # print traceback info to screen only
        import traceback
        sys.stderr.write(traceback.format_exc())
        logger.warning('cancelled by user')
    except NotConfiguredError as e:
        print('error:', e)
        if config_sub is not None:
            config_sub.print_usage()
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-except
        # print traceback info to screen only
        import traceback
        sys.stderr.write(traceback.format_exc())
        logger.error('exception occurred: %s: %s',
                     e.__class__.__name__, e)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # customize error message
        self.print_usage(sys.stderr)
        err = colored('error:', 'r', style='b')
        self.exit(2, '%s %s\n' % (err, message))


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


def _default_func(f, obj):
    def run(args):
        del args.command, args.func, args.workspace
        args = {name: value for (name, value) in args._get_kwargs()}
        args = Configuration(args)

        if f.__static__:
            return f(**args._dict())
        else:
            return f(obj, **args._dict())
    return run


def _add_config_sub(parser, argument_style):
    parser.add_argument('name', default='main', nargs='?',
                        help='module name')
    if sys.version_info < (3, 7):
        subs = parser.add_subparsers(title='modules available',
                                     dest='module')
    else:
        subs = parser.add_subparsers(title='modules available',
                                     dest='module', required=False)
    group_options = collections.defaultdict(set)

    for module, module_cls in configurables.items():
        _parser_formatter = argparse.ArgumentDefaultsHelpFormatter
        sub = subs.add_parser(module, help=module_cls.help,
                              formatter_class=_parser_formatter)
        group = sub.add_argument_group('config')

        with ParserBuilder(group, argument_style) as builder:
            mro = []
            for base_cls in module_cls.__mro__:
                mro.append(base_cls)
                if (
                    not hasattr(base_cls, '__funcspec__') or
                    not base_cls.__funcspec__.varkw
                ):
                    break
            for base_cls in reversed(mro):
                if hasattr(base_cls, '__funcspec__'):
                    for name, opt in base_cls.__funcspec__.kw:
                        builder.add_opt(name, opt)
            for submodule in module_cls.submodules:
                builder.add_opt(submodule, argspec(
                    default=submodule,
                    help='submodule ' + submodule
                ))
        for action in group._group_actions:
            group_options[module].add(action.dest)

        def save(args):
            with Workspace(args.workspace) as ws:
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
                ws.register(args.name, configurables[m],
                            **cfg._dict())

        sub.set_defaults(func=save)


def _config_default_func(args):
    ws = Workspace(args.workspace)
    cfg = ws.config_path
    if cfg.exists():
        cfg = cfg.open().read().strip()
        return cfg
    else:
        raise NotConfiguredError('no configuration in this workspace')


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


@command(
    help='clean workspace',
    description='Remove all snapshots in specific workspace by default. ' +
                'If `--all` is specified, clean the entire workspace'
)
def clean(ws,
          config=(False, 'remove workspace configuration'),
          log=(False, 'clear workspace logs'),
          snapshot=(False, 'clear snapshots'),
          everything=argspec(
              '-a', action='store_true',
              help='clear everything except for configuration'
          ),
          all=argspec('--all', action='store_true',
                      help='clean the entire workspace'),
          force=(False, 'do without confirmation')):
    """Command ``clean``.

    Remove all snapshots in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    if all:
        if not force:
            try:
                c = input('[{}] clean the entire workspace? [y/N] '.format(ws))
            except KeyboardInterrupt:
                return 1
            if c.lower() != 'y':
                return 1
        shutil.rmtree(str(ws))
    else:
        if not force:
            if everything:
                todo = ['snapshots', 'logs']
                if config:
                    todo.append('config')
            else:
                todo = []
                if snapshot:
                    todo.append('snapshots')
                if log:
                    todo.append('logs')
                if config:
                    todo.append('config')
                if len(todo) == 0:
                    todo.append('snapshots')
            msg = '[{}] clean {}? [y/N] '.format(ws, ', '.join(todo))
            try:
                c = input(msg)
            except KeyboardInterrupt:
                return 1
            if c.lower() != 'y':
                return 1
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
