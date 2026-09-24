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
import json
import os
import sys
import time

import pyrogue
import pyrogue.pydm
import rogue

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
    diagnostics = parser.add_argument_group('Transport diagnostics')
    diagnostics.add_argument('--transport-diagnostics', action='store_true',
                             help='Log startup metadata without enabling DEBUG logging')
    diagnostics.add_argument('--srp-debug', action='store_true',
                             help='Enable SRP transaction/frame DEBUG logging')
    diagnostics.add_argument('--rssi-debug', action='store_true',
                             help='Enable RSSI controller DEBUG logging')
    diagnostics.add_argument('--transaction-debug', action='store_true',
                             help='Enable memory transaction DEBUG logging (verbose)')
    diagnostics.add_argument('--column-mode', choices=('stock', 'batched', 'sequential'),
                             default='stock',
                             help='Diagnostic forceWaitEach override for ColumnBoard[0]')
    args = parser.parse_known_args()[0]
    if args.column_mode != 'stock' and args.columnBoards < 1:
        parser.error('--column-mode requires at least one column board')

    debug_filters = (
        ('SrpV3', args.srp_debug),
        ('rssi.controller', args.rssi_debug),
        ('memory.Transaction', args.transaction_debug),
    )
    for name, enabled in debug_filters:
        if enabled:
            rogue.Logging.setFilter(name, rogue.Logging.Debug)
    if any(enabled for _, enabled in debug_filters):
        rogue.Logging.setEmitStdout(True)
    log_startup = (args.transport_diagnostics or args.column_mode != 'stock'
                   or any(enabled for _, enabled in debug_filters))
    arg_dict = warm_tdm_api.arg_dict(args)

    root = warm_tdm_api.GroupRoot(**arg_dict)
    if args.column_mode != 'stock':
        # Apply before startup/initial reads; child overrides retain their scope.
        root.Group.HardwareGroup.ColumnBoard[0].forceWaitEach = args.column_mode == 'sequential'

    with root:
        if log_startup:
            print(json.dumps(dict(
                event='server_ready', epoch=time.time(), pid=os.getpid(),
                argv=sys.argv, cwd=os.getcwd(), module=__file__,
                zmq=root.zmqServer.address, column_mode=args.column_mode,
                forced_devices=[d.path for d in root.find(typ=pyrogue.Device) if d.forceWaitEach],
                root_timeout=getattr(root, '_timeout', None),
                init_write=getattr(root, '_initWrite', None),
                arguments=vars(args)), default=str), flush=True)

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
