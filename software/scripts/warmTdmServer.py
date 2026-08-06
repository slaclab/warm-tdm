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
import pyrogue
import pyrogue.pydm

import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api

parser = warm_tdm_api.WarmTdmArgparse()
args = parser.parse_known_args()[0]
arg_dict = warm_tdm_api.arg_dict(args)

with warm_tdm_api.GroupRoot(**arg_dict) as root:

    if args.docs != '':
        root.genDocuments(path=args.docs, incGroups=['DocApi'], excGroups=['NoDoc', 'Enable', 'Hardware'])

    if args.gui:
        pyrogue.pydm.runPyDM(
            serverList=root.zmqServer.address,
            title='Warm TDM',
            sizeX=2000,
            sizeY=1600,
            display=warm_tdm_api.WarmTdmDisplay)
    else:
        pyrogue.waitCntrlC()
