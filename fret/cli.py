import argparse
import collections
import logging
import shutil
import sys

from . import common
from . import util


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # customize error message
        self.print_usage(sys.stderr)
        err = util.colored('error:', 'r', style='b')
        self.exit(2, '%s %s\n' % (err, message))


main_parser = _ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter, prog='fret')

subparsers = {}


class Config(common.Command):
    """Command ``config``,

    Configure a module and its parameters for a workspace.

    Example:
        .. code-block:: bash

            $ python app.run -w ws/test config Simple -foo=5
            In [ws/test]: configured Simple with Config(foo='5')
    """

    help = 'configure module for workspace'

    def __init__(self, parser):
        super().__init__(parser)
        parser.add_argument('name', default='main', nargs='?',
                            help='module name')
        subs = parser.add_subparsers(title='modules available', dest='module')
        group_options = collections.defaultdict(set)
        try:
            _modules = common.app['modules']
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
                ws = common.Workspace(args.workspace)
                m = args.module
                config = {name: value for (name, value) in args._get_kwargs()
                          if name in group_options[m]}
                print('[%s] configured "%s" as "%s" with %s' %
                      (args.workspace, args.name, m, str(config)),
                      file=sys.stderr)
                ws.load()
                ws.add_module(args.name, _modules[m], config)
                ws.save()

            sub.set_defaults(func=save)

    def run(self, ws, args):
        config = ws.config_path.open().read().strip()
        if config:
            print(config)
        else:
            print(util.colored('warning:', 'y', style='b'),
                  'no configuration found. please run `fret config <module>`',
                  file=sys.stderr)
            self.parser.print_usage()


class Clean(common.Command):
    """Command ``clean``.

    Remove all checkpoints in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    help = 'clean workspace'

    def __init__(self, parser):
        super().__init__(parser)
        parser.add_argument('--all', action='store_true',
                            help='clean the entire workspace')
        parser.add_argument('-c', dest='config', action='store_true',
                            help='clear workspace configuration')

    def run(self, ws, args):
        if args.all:
            shutil.rmtree(str(ws))
        else:
            if args.config:
                try:
                    (ws.path / 'config.toml').unlink()
                except FileNotFoundError:
                    pass
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
    common.get_app()
    common.register_command(Config)
    common.register_command(Clean)

    main_parser.add_argument('-w', '--workspace', help='workspace dir')
    main_parser.add_argument('-q', action='store_true', help='quiet')
    main_parser.add_argument('-v', action='store_true', help='verbose')

    _subparsers = main_parser.add_subparsers(title='supported commands',
                                             dest='command')
    _subparsers.required = True

    for _cmd, _cls in common.app['commands'].items():
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

    class _ColoredFormatter(logging.Formatter):
        _LOG_COLORS = {
            'WARNING': 'y',
            'INFO': 'g',
            'DEBUG': 'b',
            'CRITICAL': 'y',
            'ERROR': 'r'
        }

        def format(self, record):
            levelname = record.levelname
            if levelname in self._LOG_COLORS:
                record.levelname = util.colored(
                    record.levelname[0],
                    self._LOG_COLORS[record.levelname],
                    style='b'
                )
            return logging.Formatter.format(self, record)

    log_formatter = _ColoredFormatter(
        '%(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    _logger.addHandler(console_handler)

    # remove logging related options
    del _args.q
    del _args.v

    real_main(_args)


if __name__ == '__main__':
    main()
