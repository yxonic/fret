"""Define commands."""
import argparse
import inspect as ins
import shutil
import sys
from collections import defaultdict

from . import common
from . import util


class Config(common.Command):
    """Command ``config``,

    Configure a model and its parameters for a workspace.

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
        subs.required = True
        group_options = defaultdict(set)
        try:
            mm = common.get_app()['module']
            _modules = {
                m[0]: m[1]
                for m in ins.getmembers(
                    mm, util.sub_class_checker(common.Module))
                if not m[0].startswith('_')}
        except ImportError:
            _modules = []

        for module in _modules:
            _parser_formatter = argparse.ArgumentDefaultsHelpFormatter
            module_cls = _modules[module]
            sub = subs.add_parser(module, help=module_cls.help,
                                  formatter_class=_parser_formatter)
            group = sub.add_argument_group('config')
            module_cls.add_arguments(group)
            for submodule in module_cls.submodules:
                group.add_argument('-' + submodule, default=submodule,
                                   help='submodule ' + submodule)
            for action in group._group_actions:
                group_options[module].add(action.dest)

            def save(args):
                ws = common.Workspace(args.workspace)
                _model = args.module
                config = {name: value for (name, value) in args._get_kwargs()
                          if name in group_options[_model]}
                print('[%s] configured "%s" as "%s" with %s' %
                      (args.workspace, args.name, _model, str(config)),
                      file=sys.stderr)
                ws.load()
                ws.add_module(args.name, getattr(mm, _model), config)
                ws.save()

            sub.set_defaults(func=save)

    def run(self, ws, args):
        pass


class Clean(common.Command):
    """Command ``clean``.

    Remove all snapshots in specific workspace. If ``--all`` is specified,
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
            shutil.rmtree(str(ws.snapshot_path))
