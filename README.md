# fret

[![Build Status](https://travis-ci.org/yxonic/fret.svg?branch=master)](https://travis-ci.org/yxonic/fret) [![Coverage Status](https://coveralls.io/repos/github/yxonic/fret/badge.svg?branch=master)](https://coveralls.io/github/yxonic/fret?branch=master)

Framework for Reproducible ExperimenTs

## API

### Basic Usage

### Workspace, Run and Module
```python
@fret.command
def resumable(ws):
    with ws.run() as run:
        i = run.acc()
        run.register(stateful)
        for e in fret.critical(run.range(10)):
            pass
```

### Inheritance
```python
@fret.configurable
class A:
    def __init__(self, foo='bar'):
        ...

@fret.configurable
class B(A):
    def __init__(self, bar=3, **others):
        super().__init__(**others)
        ...

ws = fret.workspace('/tmp/ws')
b = B(foo=0, bar=0, sth=3)
print(b.config)
```

### Internals
```python
config = fret.Configuration({'foo': 'bar'})
fret.app
```

## TODO
- [x] `fret.Configuration`: high-level class for configuration
- [ ] `fret.Workspace`: module new/save/load (by tag or by path)
- [ ] `ws.run()` context manager: `run.accumulator()`, `run.range()`, `run.register()`
- [ ] `@fret.configurable`: remove submodule, add ws parameter, parameter checking
- [ ] CLI: `fret.App`, entry point logic, testing
- [ ] Tagged workspace
- [ ] Parameter check
- [ ] Java/GNU style command line args, shorthands, better logic for boolean default value
- [ ] Global configuration file: `fret.toml`
- [ ] `fret` global app object (singleton)
- [ ] Documents and examples
- [ ] `fret new` command
- [ ] Other fret commands like show log, check module, etc.
