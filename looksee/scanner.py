"""
class Scanner
"""

import re
import os
import inspect
import importlib

from logging import Logger
from types import ModuleType
from typing import Dict, Callable, Optional, Text, Union, Any
from os.path import splitext

from appyratus.files.json import Json
from appyratus.utils.dict_utils import DictObject
from appyratus.logging import ConsoleLoggerInterface

INIT_MODULE_NAME = '__init__.py'
DOT_FILE_NAME = '.looksee'
PY_EXTENSION = 'py'


class Scanner:
    """
    The Scanner recursively walks the filesystem, relative to a dotted path to a
    Python package or module. It scans every Python module, attempting to match
    each object against a logical predicate (an arbitrary function that you
    define). When an object matches, the scanner sends it to your custom
    callback.
    """

    log = ConsoleLoggerInterface(
        'scanner', level=os.environ.get('LOOKSEE_LOG_LEVEL', 'INFO')
    )

    def __init__(
        self,
        predicate: Callable = lambda obj: True,
        callback: Callable = lambda obj: None,
        log: Optional[Logger] = None,
    ):
        self.static_context: DictObject = DictObject()
        self.context = self.static_context.copy()

        # replace class-level logger
        if log is not None:
            self.log = log

        self._predicate = predicate
        self._callback = callback

    def scan(
        self,
        package: Text,
        context: Optional[Union[Dict, DictObject]] = None,
    ):
        """
        Walk the filesystem relative to a python package, specified as a
        dotted path. For each object in each module therein, apply a
        predicate and, if True, execute a callback, like setting a value in
        self.context.
        """
        # prepare the initial runtime context dict by merging any new context
        # into a copy of the scanner's static context.
        raw_context = self.static_context.to_dict()
        if context:
            raw_context.update(context)

        # computed runtime context to pass into self.process:
        runtime_context: DictObject = DictObject(raw_context)

        root_module = importlib.import_module(package)
        root_filename = os.path.basename(root_module.__file__)

        # if we're inside a package with an __init__.py file, scan
        # it as a module. Otherwise, scan the files in the directory
        # containing the file.
        if root_filename != INIT_MODULE_NAME:
            self.scan_module(root_module, runtime_context)
        else:
            # scan the directory...
            # get information regarding our location in the filesystem
            package_dir = os.path.split(root_module.__file__)[0]
            if re.match(r'\./', package_dir):
                # ensure we use an absolute path for the package dir
                # to prevent strange string truncation results below
                package_dir = os.path.realpath(package_dir)

            package_path_len = package.count('.') + 1
            package_parent_dir = '/' + '/'.join(
                package_dir.strip('/').split('/')[:-package_path_len]
            )

            # walk the filesystem relative to our CWD
            for dir_name, sub_dirs, file_names in os.walk(package_dir):
                file_names = set(file_names)

                # check local .ravel file to see if we should skip this
                # directory.
                if DOT_FILE_NAME in file_names:
                    dot_file_path = os.path.join(dir_name, DOT_FILE_NAME)
                    dot_data = Json.read(dot_file_path) or {}
                    ignore = dot_data.get('ignore', False)
                    if ignore:
                        self.on_ignore_directory(os.path.realpath(dir_name))
                        sub_dirs.clear()
                        continue

                # scan files in the package directory
                if INIT_MODULE_NAME in file_names:
                    dir_name_offset = len(package_parent_dir)

                    # compute the dotted package path, derived from the filepath
                    pkg_path = dir_name[dir_name_offset + 1:].replace("/", ".")
                    for file_name in file_names:
                        if not file_name.endswith('.' + PY_EXTENSION):
                            continue

                        # compute dotted module path
                        mod_path = f'{pkg_path}.{splitext(file_name)[0]}'
                        try:
                            module = importlib.import_module(mod_path)
                        except Exception as exc:
                            self.on_import_error(exc, mod_path, runtime_context)
                            continue

                        # scan the module in the package directory
                        self.scan_module(module, runtime_context)

        # memoize the final context, which is the result of merging runtime
        # context generated into a copy of the static context
        self.context = runtime_context
        return self.context.copy()

    def scan_module(self, module: ModuleType, context: DictObject):
        """
        Scan a loaded python Module.
        """
        if None in module.__dict__:
            # XXX: why is this happenings?
            del module.__dict__[None]

        for k, v in inspect.getmembers(module, predicate=self.match):
            try:
                self.process(module, k, v, context)
            except Exception as exc:
                self.on_process_error(exc, module, context, k, v)

    def match(self, obj: Any) -> bool:
        """
        Perform check to see if we should apply callbacl to the given value.
        """
        is_match = self._predicate(obj)
        return is_match

    def process(
        self, module: ModuleType, name: Text, obj: Any, context: DictObject
    ):
        """
        Logic to execute upon self.predicate evaluating True for the given
        value.
        """
        self.log.debug(f'processing {name} in {module.__file__}')
        self._callback(name, obj, context)

    def on_ignore_directory(self, dirpath: Text):
        """
        Callback for when the scanner skips a directory because of a .looksee
        file.
        """
        self.log.info(message=f'ignoring directory: {dirpath}')

    def on_import_error(
        self, exc: Exception, module_path: Text, context: DictObject
    ):
        """
        Callback that executes if the scanner can't import a module because
        of an error.
        """
        self.log.exception(f'encountered import error in {module_path}')

    def on_process_error(
        self,
        exc: Exception,
        module: ModuleType,
        context: DictObject,
        name: Text,
        obj: Any
    ):
        """
        Callback that executes if the scanner encountered an error while
        scanning an imported module, with respect to a specific object contained
        therein.
        """
        self.log.exception(
            message=f'scanner encountered an error while scanning object',
            data={
                'module': module.__name__,
                'object': name,
                'type': type(obj),
            }
        )
