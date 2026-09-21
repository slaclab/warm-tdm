##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Load selected real package exports without unrelated hardware dependencies."""
import ast
import sys
from types import ModuleType


def load_package_exports(name, directory, modules):
    # Provide package shells for the focused offline/Qt tests, then execute the
    # selected import statements from the actual __init__.py in their real order.
    parts = name.split('.')
    for end in range(1, len(parts) + 1):
        package_name = '.'.join(parts[:end])
        if package_name not in sys.modules:
            package = ModuleType(package_name)
            package.__package__ = package_name
            package.__path__ = [str(directory.parents[len(parts) - end - 1]
                                    if end < len(parts) else directory)]
            sys.modules[package_name] = package
            if end > 1:
                setattr(sys.modules['.'.join(parts[:end - 1])], parts[end - 1], package)
    package = sys.modules[name]
    init_path = directory / '__init__.py'
    imported = set()
    for node in ast.parse(init_path.read_text(), filename=str(init_path)).body:
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.rsplit('.', 1)[-1]
            if module in modules:
                code = compile(ast.Module(body=[node], type_ignores=[]), str(init_path), 'exec')
                exec(code, vars(package))
                imported.add(module)
    if imported != set(modules):
        raise AssertionError(f'{init_path} is missing exports: {set(modules) - imported}')
    return package
