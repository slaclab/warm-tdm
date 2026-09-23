#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Copy a maintained notebook into a new measurement run. Does not connect to hardware."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'software/python'))
from warm_tdm_run import create_run


def main(argv=None):
    templates = ROOT / 'software/notebooks'
    choices = {str(p.relative_to(templates).with_suffix('')): p for p in templates.rglob('*.ipynb')}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template', choices=sorted(choices))
    parser.add_argument('--base', type=Path, required=True, help='Existing experiment storage directory')
    parser.add_argument('--name', required=True, help='Short measurement name')
    parser.add_argument('--purpose', default='')
    parser.add_argument('--operator')
    args = parser.parse_args(argv)
    root = create_run(choices[args.template], args.base, args.name,
                      purpose=args.purpose, operator=args.operator, repo=ROOT)
    print(root / choices[args.template].name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
