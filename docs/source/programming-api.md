# Programming API

## Workspace

### Simplist Case
```toml
# ws/test/config.toml
[main]
__module = "Model"
param = 1
```

```py
# app.py
import fret

@fret.configurable
class Model:
    def __init__(self, param=0):
        self.param = param

ws = fret.workspace('ws/test')
model = ws.build()  # or equivalently, ws.build('main')
print(model.param)  # 1
```

You can call a funtion on a workspace, even if it is wrapped as a CLI command:

```py
# app.py
import fret

@fret.configurable
class Model:
    def __init__(self, param=0):
        self.param = param

@fret.command
def check_model(ws):
    print(ws.build().param)

if __name__ == '__main__':
    ws = fret.workspace('ws/test')
    check_model(ws)
```

Then the following lines are equivalent:

```sh
$ python app.py
1
$ fret -w ws/test check_model
1
```

## App

Package can be organized to form a fret app. If you want to have access to the app, just `import fret.app`:

```py
# app.py
import fret

@fret.configurable
class Model:
    def __init__(self, param=0):
        self.param = param

@fret.command
def check_model(ws):
    print(ws.build().param)
```

```py
# main.py
import fret
import fret.app

if __name__ == '__main__':
    ws = fret.workspace('ws/test')
    fret.app.check_model(ws)
```

## CLI
```py
import fret.cli
if __name__ == '__main__':
    fret.cli.main()
```

## Package Structure
```
fret/
  __init__.py
  __main__.py
  common.py     # common public APIs
  util.py       # util types and functions
  workspace.py  # workspace related
  app.py        # app related
  cli.py        # CLI related
```
