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
import traceback

import pyrogue
import pyrogue.pydm

# --- DIAGNOSTIC: trace startup register transactions ---
# startTransaction is the single choke point for every block read/write. Print
# the variable path, direction, and a short caller stack for the first N
# transactions, so we can see WHAT is accessed at startup and WHO triggered it.
# Remove this block once diagnosed.
import pyrogue._Block as _blk
_origStartTransaction = _blk.startTransaction
_txnCount = [0]
_TXN_LIMIT = 60
def _tracedStartTransaction(block, *args, **kwargs):
    if _txnCount[0] < _TXN_LIMIT:
        _txnCount[0] += 1
        typ = kwargs.get('type', args[0] if args else '?')
        var = kwargs.get('variable', None)
        try:
            ident = var.path if var is not None else getattr(block, 'path', repr(block))
        except Exception:
            ident = repr(block)
        # Two nearest non-pyrogue-internal callers
        stack = traceback.extract_stack(limit=8)[:-1]
        callers = ' <- '.join(f'{f.name}:{f.lineno}' for f in stack[-4:])
        print(f'DBG TXN #{_txnCount[0]:02d} type={typ} var={ident}  [{callers}]', flush=True)
    return _origStartTransaction(block, *args, **kwargs)
_blk.startTransaction = _tracedStartTransaction
pyrogue.startTransaction = _tracedStartTransaction
# --- END DIAGNOSTIC ---

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

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
