##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
"""Shared entry-point implementation for the warm-tdm server scripts.

`runServer` builds a `GroupRoot` from the command-line arguments and either
launches the PyDM GUI or waits headless. The two thin scripts in
`software/scripts/` differ only in the GUI default:

- `warmTdmServer.py` runs headless unless `--gui` is passed.
- `warmTdmGui.py` launches the GUI (`forceGui=True`).
"""
import pyrogue
import pyrogue.pydm

import warm_tdm_api


def runServer(forceGui=False):
    """Build the GroupRoot from CLI args, then launch the GUI or wait headless.

    Parameters
    ----------
    forceGui : bool
        If True, always launch the PyDM GUI regardless of the ``--gui`` flag
        (used by the dedicated ``warmTdmGui.py`` entry point). If False, the GUI
        launches only when ``--gui`` is given.
    """
    parser = warm_tdm_api.WarmTdmArgparse()
    args = parser.parse_known_args()[0]
    arg_dict = warm_tdm_api.arg_dict(args)

    with warm_tdm_api.GroupRoot(**arg_dict) as root:

        if args.docs != '':
            root.genDocuments(path=args.docs, incGroups=['DocApi'], excGroups=['NoDoc', 'Enable', 'Hardware'])

        if forceGui or args.gui:
            pyrogue.pydm.runPyDM(
                serverList=root.zmqServer.address,
                title='Warm TDM',
                sizeX=2000,
                sizeY=1600,
                display=warm_tdm_api.WarmTdmDisplay)
        else:
            pyrogue.waitCntrlC()
