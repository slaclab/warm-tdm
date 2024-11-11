#!/usr/bin/env python3

import rogue
import pyrogue.pydm
import sys
import argparse
import os
import logging

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm
import warm_tdm_api

#rogue.Logging.setFilter('pyrogue.batcher', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
# rogue.Logging.setLevel(rogue.Logging.Warning)
# rogue.Logging.setLevel(rogue.Logging.Debug)
# rogue.Logging.setFilter("pyrogue.rssi",rogue.Logging.Info)
# rogue.Logging.setFilter("pyrogue.packetizer",rogue.Logging.Info)
# rogue.Logging.setLevel(rogue.Logging.Debug)

#rogue.Logging.setFilter('pyrogue.rssi', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.udp', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.udp', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.packetizer', rogue.Logging.Debug)

#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10000', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10002', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10004', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10006', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10008', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10010', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#logging.getLogger('pyrogue.SideBandSim').setLevel(logging.DEBUG)

# Set the argument parser
parser = warm_tdm_api.WarmTdmArgparse()

args = parser.parse_known_args()[0]
print(args)

arg_dict = warm_tdm_api.arg_dict(args)

with warm_tdm.WarmTdmRoot(**arg_dict) as root:

    print('Built root. Starting PyDM')

    pyrogue.pydm.runPyDM(
        serverList=root.zmqServer.address,
        title='Warm TDM',
        sizeX=2000,
        sizeY=1600,
        ui=warm_tdm_api.pydmUi)
