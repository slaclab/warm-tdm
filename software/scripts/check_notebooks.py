#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Check template notebook structure and cleared outputs without modifying files.

Uses only the standard library. Checks the notebook/cell envelope, not Python
execution or MIME payload schemas; IPython magics and markdown attachments are
allowed. Historical records, run copies and Jupyter checkpoints are excluded.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2] / 'software/notebooks'


def validate(notebook):
    """Raise ValueError for malformed structure or executed template cells."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(isinstance(notebook, dict), 'Notebook must be an object')
    require(notebook.get('nbformat') == 4, 'Expected notebook format 4')
    minor = notebook.get('nbformat_minor')
    require(type(minor) is int and minor >= 0, 'Invalid nbformat_minor')
    require(isinstance(notebook.get('metadata'), dict), 'Missing notebook metadata')
    cells = notebook.get('cells')
    require(isinstance(cells, list) and bool(cells), 'Template must contain cells')
    ids = set()
    for index, cell in enumerate(cells):
        label = f'Cell {index + 1}'
        require(isinstance(cell, dict), f'{label}: expected an object')
        kind = cell.get('cell_type')
        require(kind in ('code', 'markdown', 'raw'), f'{label}: invalid cell type')
        require(isinstance(cell.get('metadata'), dict), f'{label}: missing metadata')
        source = cell.get('source')
        require(isinstance(source, str) or
                (isinstance(source, list) and all(isinstance(line, str) for line in source)),
                f'{label}: source must be text or a list of text lines')
        if minor >= 5 or 'id' in cell:
            cell_id = cell.get('id')
            require(isinstance(cell_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', cell_id),
                    f'{label}: missing or invalid cell id')
            require(cell_id not in ids, f'{label}: duplicate cell id')
            ids.add(cell_id)
        if kind == 'code':
            require(cell.get('outputs') == [], f'{label}: clear outputs before saving the template')
            require('execution_count' in cell and cell['execution_count'] is None,
                    f'{label}: clear execution count before saving the template')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    paths = sorted(path for path in ROOT.rglob('*.ipynb')
                   if not any(part.startswith('.') for part in path.relative_to(ROOT).parts))
    if not paths:
        print(f'No notebook templates found in {ROOT}')
        return 1
    failures = 0
    for path in paths:
        try:
            validate(json.loads(path.read_text()))
        except (OSError, ValueError) as exc:
            print(f'{path.relative_to(ROOT)}: {exc}')
            failures += 1
    if not failures:
        print(f'Checked {len(paths)} output-free notebook templates')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
