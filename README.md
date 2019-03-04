# fret

[![PyPI](https://img.shields.io/pypi/v/fret.svg)](https://pypi.python.org/pypi/fret)
[![Travis (.org)](https://img.shields.io/travis/yxonic/fret.svg)](https://travis-ci.org/yxonic/fret)
[![Coveralls github](https://img.shields.io/coveralls/github/yxonic/fret.svg)](https://coveralls.io/github/yxonic/fret?branch=master)

Framework for Reproducible ExperimenTs

## Installation
From pip:
```sh
pip install fret
```

From source: clone the repository and then run: `python setup.py install`.

## Tutorial

### Basic Usage

Create a file named `app.py` with content:
```python
import fret

@fret.command
def run(ws):
    model = ws.build()
    print(model)

@fret.configurable
class Model:
    def __init__(self, x=3, y=4):
        ...
```

Then under the same directory, you can run: 
```sh
$ fret config Model
[ws/_default] configured "main" as "Model" with: x=3, y=4
$ fret run
Model(x=3, y=4)
$ fret config Model -x 5 -y 10
[ws/_default] configured "main" as "Model" with: x=5, y=10
$ fret run
Model(x=5, y=10)
```

### Using Workspace

You can specify different configuration in different workspace:
```sh
$ fret -w ws/model1 config Model
[ws/model1] configured "main" as "Model" with: x=3, y=4
$ fret -w ws/model2 config Model -x 5 -y 10
[ws/model2] configured "main" as "Model" with: x=5, y=10
$ fret -w ws/model1 run
Model(x=3, y=4)
$ fret -w ws/model2 run
Model(x=5, y=10)
```

You can ommit `-w <path>` if you are currently under a workspace:
```sh
$ cd ws/model2
$ fret run
Model(x=5, y=10)
```

### Save/Load
[TODO]

### An Advanced Workflow

In `app.py`:
```python
import time
import fret

@fret.configurable
@fret.stateful(['value'])
class Model:
    def __init__(self):
        self.value = 0

@fret.command
def resumable(ws):
    model = ws.build()
    with ws.run('exp-1') as run:
        run.register(model)
        cnt = run.acc()
        for e in fret.nonbreak(run.range(5)):
            # with `nonbreak`, the program always finish this loop before exit
            model.value += e
            time.sleep(0.2)
            cnt += 1
            print('current epoch: %d, sum: %d, cnt: %d' %
                  (e, model.value, cnt))
```

Then you can stop and restart this program anytime, with consistent results:
```sh
$ fret resumable
current epoch: 0, sum: 0, cnt: 1
current epoch: 1, sum: 1, cnt: 2
^CW SIGINT received. Delaying KeyboardInterrupt.
current epoch: 2, sum: 3, cnt: 3
Traceback (most recent call last):
    ...
KeyboardInterrupt
W cancelled by user
$ fret resumable
current epoch: 3, sum: 6, cnt: 4
current epoch: 4, sum: 10, cnt: 5
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
```

```sh
$ fret config a A -foo test
[ws/_default] configured "a" as "A" with: foo='test'
$ fret config B
[ws/_default] configured "main" as "B" with: a='a', bar=3
$ fret run
B(A(foo='test'), bar=4)
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
```

```sh
$ fret config B -foo baz -bar 0
[ws/_default] configured "main" as "B" with: bar=0, foo='baz', sth=3
$ fret run
B(bar=0, foo='baz', sth=3)
```

### Internals
```python
>>> config = fret.Configuration({'foo': 'bar'})
>>> config
foo='bar'
```

## TODO
- [x] `fret.Configuration`: high-level class for configuration
- [x] `fret.Workspace`: module build/save/load (by tag or by path), persistency
- [x] `ws.run()` context manager, `run.value()`, `run.acc()`, `run.range()`, `run.register()`
- [ ] `@fret.configurable`: parameter checking
- [x] `fret.App`, global app object
- [ ] CLI: entry point logic, testing, tagged workspace
- [ ] Java/GNU style command line args, shorthands, better logic for boolean default value
- [ ] Global configuration file: `fret.toml`
- [ ] Documents and examples
- [ ] `fret new` command with interactive CLI
- [ ] Other fret commands like show log, check module, etc.
