import importlib
import sys
import toml


def find_app():
    sys.path.append('.')
    config = toml.load(open('.repe.toml'))
    models = importlib.import_module(config['appname'] + '.models')
    command = importlib.import_module(config['appname'] + '.command')
    return models, command


models, command = find_app()
