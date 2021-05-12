# Looksee Python Module Scanner
Looksee is a tool for scanning Python packages for objects that match a custom
predicate, and when there's a match, performing a custom callback, like adding
each object to a global registry of some kind or triggering logic as an import
side-effect.

It's similar to
[Venusian](https://docs.pylonsproject.org/projects/venusian/en/latest/) but far
less annoying. Venusian can be a pain in the arse when it comes to handling
errors. Often times, you're left scratching your head, trying to figure out
what, if anything, went wrong.

## Install Looksee
Clone the repo or just run...
```sh
pip install looksee
```

## Basic Example
Here's an example of looksee's `Scanner` being used to scan a fictitious
package, called `pooply`, for all `PooplyObject` subclasses. When found, we add
each one to a growing "context" dict. Note that the `scan` method returns a
shallow copy of the context dict, memoizing the original in `scanner.context`.


```python

from looksee import Scanner
from pooply.base import PooplyObject

scanner = Scanner(
    predicate=lambda: obj: issubclass(obj, PooplyObject),
    callback=lambda name, obj, ctx: ctx.update({name: obj})
)

found = scanner.scan('pooply')

for name, class_obj in found.items():
    print(f'detected {name} class: {class_obj}...')
```

## Use-cases

### Class Factory Pattern
Suppose you have a config file that specifies the name of a class to use in your
application. To translate the name of the class to an actual class object, you
write code like this:

```python
from project.models.user import User
from project.models.account import Account

class Model:

    @classmethod
    def factory(cls, class_name: Text) -> Type:
        if class_name == 'User':
            return User
        if class_name == 'Account':
            return Account
        else:
            raise TypeError(class_name)
```

By itself, this seems fine, but when you try to run it, you realize that you've
caused a bunch of cyclic import errors by trying to import each subclass into
the module containing its base class. Not only that, but the if-statement must
be keep up-to-date manually with each new class added to the application. To fix
the import errors, you could try moving each import into the `factory` function
itself, but this would be bad form, and you would still have to update the
if-statement with each new class.

By using looksee, you could avoid this altogether by doing something like:

```python
from looksee import Scanner

class Model:

    # lazy loaded global registry of model subclasses
    model_classes = {}

    # scanner that detects Model subclasses
    scanner = Scanner(
        predicate=lambda obj: issubclass(obj, cls),
        callback=lambda name, obj, ctx: ctx.update({name: obj})
    )

    @classmethod
    def factory(cls, class_name: Text) -> Type:
        # lazily scan resource modules, picking up subclasses
        if not cls.model_classes:
            cls.model_classes = cls.scanner.scan('project.resources')

        # return the named class from the model_classes dict
        model_class = cls.model_classes.get(class_name)
        if model_class is None:
            raise TypeError(class_name)

        return model_class
```

### Endpoint/Function Registration in a Framework
Most Python web frameworks use decorators to register endpoints. It's likely that you've seen some form of...

```python
@app.get(url='/users/{user_id}')
def get_user(request, user_id):
    return User.get(user_id)
```

Internally, `app.get()` adds the `get_user` function to the app as a route. In
order to detect each endpoint, the framework must be able to scan the modules
contained a project, evaluating decorators as a side-effect. Looksee can be
used for cases like this. Here is a sketch of how you might achieve this:

```python
class Application(HttpServer):
    def __init__(self, package: Text):
        self.routes = []
        self.scanner = Scanner()
        self.package = package

    def start(self):
        self.scanner.scan(self.package)
        self.serve_forever()

    def get(self, url: Text):
        """ Register an HTTP GET route """
        return Decorator(self, 'GET', url)

    def post(self, url: Text):
        """ Register an HTTP POST route """
        return Decorator(self, 'POST', url)
        

class Decorator:
    def __init__(self, app, method: Text, url: Text):
        self.app = app
        self.method = method
        self.url = url

    def __call__(self, func: Callable):
        self.app.routes.append(Route(url, func))


class Route:
    def __init__(self, method: Text, url: Text, func: Callable):
        self.method = method
        self.url = url
        self.func = func
```

Now, when someone using your framework calls `app.start()`, the app's scanner
will trigger each decorator in whatever module it resides, simply as a side-effect of being
imported. This might look something like:

```python
# file: app.py

app = Application('my_project')
app.start()
```

```python
# file: routes.py

from .app import app

@app.get('/users/{user_id}')
def get_user(request, user_id):
    return User.get(user_id)
```

## Working Example
A complete working example in which a `Scanner` is used to scan a fictitious project
is located in the `example/` directory. To run it, just do: 
```sh
python ./example/scan.py
```

## Event Hooks
A couple things can go wrong while performing a scan: either (1) a module cannot
be imported due to an error or (2) your callback raises an exception while
processing an object. You can override `Scanner` hook base methods to deal with
both of these cases.

### Import Error Hook
```python
def on_import_error(
    self, exc: Exception, module_path: Text, context: Dict
):
    """
    Executes if the scanner can't import a module because of an error.
    """
````

### Callback Error Hook
```python
def on_callback_error(
    self, exc: Exception, module: ModuleType, context: Dict, name: Text, obj: Any
):
    """
    Execute if scanner encountered error inside custom callback function
    """
````

### Ignore Directory Hook
In addition to handling errors, the scanner can be directed to skip certain
directories. To do so, it looks for a `.looksee` JSON file in the directory to
skip. That file should contain a JSON object like:
```json
{
  "ignore": true
}
```

If the scanner determines that it should ignore a directory, it triggers its
`on_ignore_directory` hook:
```python
def on_ignore_directory(self, dirpath: Text):
    """
    Executes when scanner skips a directory because of .looksee file.
    """
```

## Logging
You can easily toggle the internal log level by either setting the
`LOOKSEE_LOG_LEVEL` environment variable or by passing a custom logger into the
`Scanner` initializer.

## Questions & Comments
If you have any questions or comments, feel free to open an issue or email us directly. We appreciate your contributions and support!