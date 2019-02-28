import argparse
import collections
import logging
import shutil
import sys

from . import common
from . import util
from .app import app, Command


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # customize error message
        self.print_usage(sys.stderr)
        err = util.colored('error:', 'r', style='b')
        self.exit(2, '%s %s\n' % (err, message))


main_parser = _ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter, prog='fret')

subparsers = {}


class config(Command):
    """Command ``config``,

    Configure a module and its parameters for a workspace.

    Example:
        .. code-block:: bash

            $ python app.run -w ws/test config Simple -foo=5
            In [ws/test]: configured Simple with Config(foo='5')
    """

    help = 'configure module for workspace'

    def __init__(self, parser):
        parser.add_argument('name', default='main', nargs='?',
                            help='module name')
        subs = parser.add_subparsers(title='modules available', dest='module')
        group_options = collections.defaultdict(set)
        try:
            _modules = app._modules
        except ImportError:
            _modules = {}

        for module, module_cls in _modules.items():
            _parser_formatter = argparse.ArgumentDefaultsHelpFormatter
            sub = subs.add_parser(module, help=module_cls.help,
                                  formatter_class=_parser_formatter)
            group = sub.add_argument_group('config')
            module_cls._add_arguments(group)
            for action in group._group_actions:
                group_options[module].add(action.dest)

            def save(args):
                ws = app.workspace(args.workspace)
                m = args.module
                cfg = {name: value for (name, value) in args._get_kwargs()
                       if name in group_options[m]}
                print('[%s] configured "%s" as "%s" with %s' %
                      (ws, args.name, m, str(cfg)),
                      file=sys.stderr)
                ws.register(args.name, app.load_module(m), **cfg)

            sub.set_defaults(func=save)

    def run(self, ws, args):
        cfg = ws.config_path.open().read().strip()
        if cfg:
            print(cfg)
        else:
            raise common.NotConfiguredError


class clean(Command):
    """Command ``clean``.

    Remove all checkpoints in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    help = 'clean workspace'

    def __init__(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='clean the entire workspace')
        parser.add_argument('-c', dest='config', action='store_true',
                            help='clear workspace configuration')
        parser.add_argument('-l', dest='log', action='store_true',
                            help='clear workspace logs')

    def run(self, ws, args):
        if args.all:
            shutil.rmtree(str(ws))
        else:
            if args.config:
                try:
                    (ws.path / 'config.toml').unlink()
                except FileNotFoundError:
                    pass
            if args.log:
                shutil.rmtree(str(ws.log_path))
            else:
                shutil.rmtree(str(ws.checkpoint_path))


def real_main(args):
    logger = logging.getLogger(args.command)
    try:
        return args.func(args)
    except KeyboardInterrupt:  # pragma: no cover
        # print traceback info to screen only
        import traceback
        sys.stderr.write(traceback.format_exc())
        logger.warning('cancelled by user')
    except common.NotConfiguredError as e:  # pragma: no cover
        print('error:', e)
        subparsers['config'].print_usage()
        sys.exit(1)
    except Exception as e:  # pragma: no cover
        # print traceback info to screen only
        import traceback
        sys.stderr.write(traceback.format_exc())
        logger.error('exception occurred: %s', e)


def main(args=None):
    app.register_command(config)
    app.register_command(clean)
    app.import_modules()

    main_parser.add_argument('-w', '--workspace', help='workspace dir')
    main_parser.add_argument('-q', action='store_true', help='quiet')
    main_parser.add_argument('-v', action='store_true', help='verbose')

    _subparsers = main_parser.add_subparsers(title='supported commands',
                                             dest='command')
    _subparsers.required = True

    for _cmd, _cls in app._commands.items():
        _sub = _subparsers.add_parser(
            _cmd, help=_cls.help,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        subparsers[_cmd] = _sub
        _sub.set_defaults(func=_cls(_sub)._run)

    _args = main_parser.parse_args() if args is None \
        else main_parser.parse_args(args)

    # configure logger
    _logger = logging.getLogger()
    if _args.q:
        _logger.setLevel(logging.WARNING)
    elif _args.v:
        _logger.setLevel(logging.DEBUG)
    else:
        _logger.setLevel(logging.INFO)

    # remove logging related options
    del _args.q
    del _args.v

    real_main(_args)


if __name__ == '__main__':
    main()
