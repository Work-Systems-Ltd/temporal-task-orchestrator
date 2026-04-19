import importlib
import os
import pkgutil

_pkg_dir = os.path.dirname(__file__)
for _importer, _modname, _ispkg in pkgutil.iter_modules([_pkg_dir]):
    importlib.import_module(f"{__name__}.{_modname}")
