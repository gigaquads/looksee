# Looksee Python Module Scanner
Looksee is a nifty little utility for scanning Python packages (or individual
modules), looking for objects that match a custom logical predicate, and when
there's a match, performing custom callback logic -- like adding the the matched
object to a global registry of some kind.

It's similar to
[Venusian](https://docs.pylonsproject.org/projects/venusian/en/latest/) but far
less annoying. Venusian can be a true pain in the arse when it comes to handling
errors. Often times, you're left scratching your head, trying to figure out
what, if anything, went wrong.

## Basic Example
Here's an example of looksee's API. It consists of one main `Scanner` class. In
the example, we scan a fictitious package called `pooply` for all `PooplyObject`
subclasses. When found, we simply add it to the context dict. Note that the
`scan` method returns a shallow copy of the context dict while memoizing the
original as `scanner.context`.


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

### Class Factories
Sometimes the need arises to get a class by name. For example, imagine you have a YAML config file that specifies a class by name. In Python, you need to take the name and return the class object itself. As a result, you may have a function that looks like this:

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

All is well and good, but sometimes importing a bunch of classes into a single
module can cause cyclic import errors. To prevent this, you could always move
the imports into the `factory` function itself, but this is bad form. By using
the looksee `Scanner`, you could avoid all of this:

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
        if not cls.registry:
            cls.model_classes = cls.scanner.scan('project.resources')

        # return the named class from the model_classes dict
        model_class = cls.model_classes.get(class_name)
        if model_class is None:
            raise TypeError(class_name)

        return model_class
```

### Object Registries

## Example Application
A complete working example of a scanner being used to scan a fictitious project
is located in the `example/` directory. To run it, just do: 
```sh
python example/scan.py
```

## Event Hooks
A couple things can go wrong while performing a scan: either a module cannot be
imported due to an error or your callback raises an exception while processing
an object. You can override two `Scanner` hook methods to deal with these two
cases.

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