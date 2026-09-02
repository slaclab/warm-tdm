#!/usr/bin/env python3
##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
"""Shared scaffolding for the hardware-test helper scripts.

These scripts live one directory below ``software/scripts/``, so we put that
directory on ``sys.path`` and reuse the repo's ``_setupLibPaths`` to register
the in-repo ``warm_tdm``/``warm_tdm_api``/surf library paths — same mechanism as
every other script in ``software/scripts/``.

Provides:
  * ``add_conn_args(parser)``  — the shared ``--host``/``--port`` options.
  * ``connect(args)``          — open an operations ``Session`` and print the
                                 firmware build stamps (pin the result to a
                                 firmware/software version).
  * ``Checklist``              — accumulate PASS/FAIL lines mirroring a wiki
                                 page's pass criteria; ``.report()`` prints them
                                 and returns a process exit code.
"""
import os
import sys

# Make the parent scripts dir importable so `_setupLibPaths` (which resolves the
# repo tree relative to software/scripts/) can be reused as-is.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..'))

import _setupLibPaths  # noqa: E402,F401  (registers in-repo library paths)

import warm_tdm_api.operations as ops  # noqa: E402


def add_conn_args(parser):
    """Add the connection flags shared by every hwtest script."""
    parser.add_argument('--host', type=str, default='localhost',
                        help='warmTdmServer host (default: localhost)')
    parser.add_argument('--port', type=int, default=9099,
                        help='warmTdmServer ZMQ port (default: 9099)')
    return parser


def connect(args):
    """Connect an operations Session and print the firmware build stamps.

    Returns the Session. The build-stamp print is deliberately unconditional:
    every hwtest result must be pinned to a specific firmware + software version,
    so the output is meant to be pasted into the wiki Record block / the issue.
    """
    sess = ops.connect(host=args.host, port=args.port)
    print('=' * 72)
    print(f'Connected to {args.host}:{args.port}')
    print('-' * 72)
    try:
        ops.print_hardware()   # per-board BuildStamp + git hash
    except Exception as exc:   # never let a diagnostic print sink the run
        print(f'(could not read hardware build stamps: {exc})')
    print('=' * 72)
    return sess


class Checklist:
    """Collect pass/fail items that mirror a wiki page's 'Pass criteria'.

    Each ``item(ok, label, detail)`` records one check; ``report()`` prints the
    block and returns 0 if every item passed, 1 otherwise (so a script can
    ``sys.exit(checklist.report())``).
    """

    def __init__(self, title):
        self.title = title
        self._items = []

    def item(self, ok, label, detail=''):
        self._items.append((bool(ok), label, detail))
        mark = 'PASS' if ok else 'FAIL'
        line = f'  [{mark}] {label}'
        if detail:
            line += f'  — {detail}'
        print(line)
        return ok

    def note(self, text):
        """A non-pass/fail informational line (e.g. a manual step reminder)."""
        print(f'  [ .. ] {text}')

    def report(self):
        passed = sum(1 for ok, _, _ in self._items if ok)
        total = len(self._items)
        allok = passed == total and total > 0
        print('-' * 72)
        print(f'{self.title}: {passed}/{total} checks passed — '
              f'{"PASS" if allok else "FAIL"}')
        print('=' * 72)
        return 0 if allok else 1


def finish(code):
    """Terminate a hwtest script immediately with ``code``.

    The rogue ``VirtualClient`` (ZMQ) spins up non-daemon background threads that
    are never joined, so a normal ``return``/``sys.exit`` leaves the interpreter
    hanging after the report prints. These scripts are one-shot diagnostics whose
    last action is always the checklist report, so a hard exit (after flushing
    output) is the pragmatic clean end. Use as ``return finish(chk.report())``.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
