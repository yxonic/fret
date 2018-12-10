import argparse
import inspect as ins
import logging
import sys

from . import command
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


def main():
    main_parser.add_argument('-w', '--workspace',
                             help='workspace dir', default='ws/test')
    main_parser.add_argument('-q', action='store_true', help='quiet')
    main_parser.add_argument('-v', action='store_true', help='verbose')

    _subparsers = main_parser.add_subparsers(title='supported commands',
                                             dest='command')
    _subparsers.required = True

    _commands = {m[0].lower(): m[1]
                 for m in ins.getmembers(command,
                                         util.sub_class_checker(
                                             common.Command))}

    c = common.get_app()['command']
    _commands.update(
        {m[0].lower(): m[1]
         for m in ins.getmembers(c,
                                 util.sub_class_checker(common.Command))}
    )

    for _cmd, _cls in _commands.items():
        _sub = _subparsers.add_parser(
            _cmd, help=_cls.help,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        subparsers[_cmd] = _sub
        _sub.set_defaults(func=_cls(_sub)._run)

    _args = main_parser.parse_args()

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
