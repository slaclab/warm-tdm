#!/usr/bin/env python3

import rogue
import pyrogue.gui
import sys
import argparse
import os
import logging

if '--local' in sys.argv:
    baseDir = os.path.dirname(os.path.realpath(__file__))
    print(f'{baseDir}/../../firmware/python')
    pyrogue.addLibraryPath(f'{baseDir}/../../firmware/python')
    pyrogue.addLibraryPath(f'{baseDir}/../../firmware/submodules/surf/python')


import warm_tdm

#rogue.Logging.setFilter('pyrogue.batcher', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)

#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10000', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10002', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10004', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10006', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10008', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore.localhost.Client.10010', rogue.Logging.Debug)
rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#logging.getLogger('pyrogue.SideBandSim').setLevel(logging.DEBUG)

# Set the argument parser
parser = argparse.ArgumentParser()

parser.add_argument(
    "--sim",
    action = 'store_true',
    default = False)

groups = [{
    'host': '192.168.3.11',
    'colBoards': 0,
    'rowBoards': 1}]


# parser.add_argument(
#     "--debug", 
#     required = False,
#     action = 'store_true',
#     help     = "enable auto-polling",
# )

args = parser.parse_known_args()[0]
print(args)

kwargs = {}
kwargs['simulation'] = args.sim
kwargs['groups'] = groups

print(kwargs)

with warm_tdm.WarmTdmRoot(pollEn=False, **kwargs) as root:

    # Create GUI
    appTop = pyrogue.gui.application(sys.argv)
    guiTop = pyrogue.gui.GuiTop()
    guiTop.addTree(root)
    guiTop.resize(1000,1000)

    # Run gui
    appTop.exec_()
