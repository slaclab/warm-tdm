#!/usr/bin/env python3
import argparse
import logging

import pyrogue
import pyrogue.pydm
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api
import warm_tdm

from warm_tdm_api import PhysicalMap as pm

#rogue.Logging.setFilter('pyrogue.memory.block', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Master', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Hub', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Transaction', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Variable.RemoteVariable.GroupRoot.Group.HardwareGroup.RowBoard[0]').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#rogue.Logging.setFilter('pyrogue.packetizer', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.packetizer.Controller', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.packetizer.Application', rogue.Logging.Debug)
#rogue.Logging.setLevel(rogue.Logging.Debug)


# Set the argument parser
parser = warm_tdm_api.WarmTdmArgparse()

args = parser.parse_known_args()[0]
print(args)

arg_dict = warm_tdm_api.arg_dict(args)

with warm_tdm_api.GroupRoot(**arg_dict) as root:

    if args.docs != '':
        root.genDocuments(path=args.docs,incGroups=['DocApi'],excGroups=['NoDoc','Enable','Hardware'])

#    root.Group.ColTuneEnable.set(False, index=0)
#    root.Group.ColTuneEnable.set(False, index=1)

#     root.Group.RowIndexOrderList.set([0, 1, 2, 3])
#     colTuneEnable = [False for _ in range(8)]
#     colTuneEnable[4] = True
#     root.Group.ColTuneEnable.set(colTuneEnable)

    print('Built root. Starting PyDM')
    
#    root.Group.HardwareGroup.RowBoard[0].enable.set(False)


    pyrogue.pydm.runPyDM(
        serverList=root.zmqServer.address,
        title='Warm TDM',
        sizeX=2000,
        sizeY=1600,
        ui=warm_tdm_api.pydmUi)


