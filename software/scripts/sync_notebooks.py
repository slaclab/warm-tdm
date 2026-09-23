#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Generate/check curated notebooks from the repository's simple percent-cell sources.

Supports # %% code cells and # %% [markdown] cells. Notebook magics are written
as # %... in code cells. This intentionally does not parse general Jupytext
metadata; copied measurement notebooks are never synchronized by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2] / 'software/notebooks'


def notebook(source):
    parts = re.split(r'^# %%( \[markdown\])?\s*\n', source, flags=re.M)
    cells = []
    for i in range(1, len(parts), 2):
        markdown = parts[i] is not None
        lines = parts[i + 1].strip('\n').splitlines()
        if markdown:
            lines = [line[2:] if line.startswith('# ') else '' if line == '#' else line for line in lines]
        else:
            lines = [line[2:] if line.startswith('# %') else line for line in lines]
        text = '\n'.join(lines)
        cell = dict(cell_type='markdown' if markdown else 'code', metadata={},
                    id=hashlib.sha256((str(i) + text).encode()).hexdigest()[:12],
                    source=text.splitlines(keepends=True))
        if not markdown:
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    if not cells:
        raise ValueError('Source contains no percent cells')
    return dict(cells=cells, metadata=dict(kernelspec=dict(display_name='Python 3', language='python', name='python3'),
                                         language_info=dict(name='python')),
                nbformat=4, nbformat_minor=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    failures = []
    if args.check:
        failures.extend(str(path.relative_to(ROOT)) for path in ROOT.rglob('*.ipynb')
                        if not path.with_suffix('.py').is_file())
    for source in sorted(ROOT.rglob('*.py')):
        target = source.with_suffix('.ipynb')
        expected = json.dumps(notebook(source.read_text()), indent=1) + '\n'
        if args.check:
            if not target.exists() or target.read_text() != expected:
                failures.append(str(target.relative_to(ROOT)))
        else:
            target.write_text(expected)
    if failures:
        print('Regenerate notebooks: ' + ', '.join(failures))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
