# fret

[![Build Status](https://travis-ci.org/yxonic/fret.svg?branch=master)](https://travis-ci.org/yxonic/fret) [![Coverage Status](https://coveralls.io/repos/github/yxonic/fret/badge.svg?branch=master)](https://coveralls.io/github/yxonic/fret?branch=master)

Framework for Reproducible ExperimenTs

## API

### Basic Usage

### Building CLI

### An Advanced Workflow
```python
@fret.command
def resumable(ws):
    with ws.run() as run:
        i = run.acc()
        run.register(stateful)
        for e in fret.nonbreak(run.range(10)):
            pass
```

### Submodule
```python
@fret.configurable
class A:
    def __init__(self, foo='bar'):
        ...

@fret.configurable(submodules=['a'])
class B:
    def __init__(self, a, bar=3):
        ...

>>> ws = fret.workspace('/tmp/ws')
>>> a = A()
>>> b = B(a, bar=4)
>>> b
B(A(foo='bar'), bar=4)
```

### Inheritance
```python
@fret.configurable
class A:
    def __init__(self, foo='bar', sth=3):
        ...

@fret.configurable
class B(A):
    def __init__(self, bar=3, **others):
        super().__init__(**others)
        ...

>>> ws = fret.workspace('/tmp/ws')
>>> b = B(foo=0, bar=0)
>>> b
B(foo=0, bar=0, sth=3)
```

### Internals
```python
>>> config = fret.Configuration({'foo': 'bar'})
>>> config
foo='bar'
```

## TODO
- [x] `fret.Configuration`: high-level class for configuration
- [x] `fret.Workspace`: module build/save/load (by tag or by path)
- [ ] `ws.run()` context manager, `run.value()`, `run.acc()`, `run.range()`, `run.register()`
- [ ] `@fret.configurable`: add ws parameter, parameter checking
- [x] `fret.App`, global app object
- [ ] CLI: entry point logic, testing, tagged workspace
- [ ] Parameter check
- [ ] Java/GNU style command line args, shorthands, better logic for boolean default value
- [ ] Global configuration file: `fret.toml`
- [ ] Documents and examples
- [ ] `fret new` command with interactive CLI
- [ ] Other fret commands like show log, check module, etc.
