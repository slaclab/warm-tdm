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
"""Shared PyRogue library-path setup for warm-tdm scripts.

Import this module (``import _setupLibPaths``) before importing ``warm_tdm`` or
``warm_tdm_api`` from any script in ``software/scripts/``. It registers the
in-repo ``warm_tdm_api``, ``warm_tdm`` and surf ``python`` directories with
PyRogue.

Paths are resolved relative to this file, so scripts work regardless of the
current working directory (the previous per-script ``../python`` relative paths
only worked when run from ``software/scripts/``).
"""
import os

import pyrogue

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOP = os.path.realpath(os.path.join(_HERE, '..', '..'))

pyrogue.addLibraryPath(os.path.join(_TOP, 'software', 'python'))
pyrogue.addLibraryPath(os.path.join(_TOP, 'firmware', 'python'))
pyrogue.addLibraryPath(os.path.join(_TOP, 'firmware', 'submodules', 'surf', 'python'))
