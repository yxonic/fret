"""Define commands."""
import argparse
import inspect as ins
import shutil
import sys
from collections import defaultdict

from . import common
from . import util


class Clean(common.Command):
    """Command ``clean``.

    Remove all snapshots in specific workspace. If ``--all`` is specified,
    clean the entire workspace
    """

    def __init__(self, parser):
        super().__init__(parser)
        parser.add_argument('--all', action='store_true',
                            help='clean the entire workspace')

    def run(self, ws, args):
        if args.all:
            shutil.rmtree(str(ws))
        else:
            shutil.rmtree(str(ws.snapshot_path))


class Config(common.Command):
    """Command ``config``,

    Configure a model and its parameters for a workspace.

    Example:
        .. code-block:: bash

            $ python app.run -w ws/test config Simple -foo=5
            In [ws/test]: configured Simple with Config(foo='5')
    """

    def __init__(self, parser):
        super().__init__(parser)
        subs = parser.add_subparsers(title='models available', dest='model')
        subs.required = True
        group_options = defaultdict(set)
        try:
            from .app import models as mm
            _models = {
                m[0]: m[1]
                for m in ins.getmembers(mm, util.sub_class_checker(mm.Model))
                if not m[0].startswith('_')}
        except ImportError:
            _models = []

        for model in _models:
            _parser_formatter = argparse.ArgumentDefaultsHelpFormatter
            sub = subs.add_parser(model, formatter_class=_parser_formatter)
            group = sub.add_argument_group('config')
            model_cls = _models[model]
            model_cls.add_arguments(group)
            # noinspection PyProtectedMember
            for action in group._group_actions:
                group_options[model].add(action.dest)

            # noinspection PyProtectedMember
            def save(args):
                _model = args.model
                config = {name: value for (name, value) in args._get_kwargs()
                          if name in group_options[_model]}
                model_cls._unfold_config(config)
                print('In [%s]: configured %s with %s' %
                      (args.workspace, _model, str(config)),
                      file=sys.stderr)

                common.Workspace(args.workspace, _model, config)

            sub.set_defaults(func=save)

    def run(self, ws, args):
        pass
