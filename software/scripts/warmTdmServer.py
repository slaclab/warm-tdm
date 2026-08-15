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
"""Start the Warm-TDM server (headless).

Builds the GroupRoot and waits. Pass --gui to also launch the PyDM display, or
run warmTdmGui.py for a GUI-by-default launcher.
"""
import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api

warm_tdm_api.runServer()
