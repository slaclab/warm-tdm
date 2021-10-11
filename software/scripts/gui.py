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
parser = argparse.ArgumentParser()

parser.add_argument(
    "--sim",
    action = 'store_true',
    default = False)

parser.add_argument(
    "--emulate",
    action = 'store_true',
    default = False)

parser.add_argument(
    "--ip",
    type     = str,
    required = False,
    default = '192.168.3.12',
    help     = "IP address")

parser.add_argument(
    "--groups",
    type     = int,
    help     = "Number of hardware groups")

parser.add_argument(
    "--rows",
    type     = int,
    help     = "Number of row modules")

parser.add_argument(
    "--cols",
    type     = int,
    help     = "Number of column modules")

parser.add_argument(
    "--plots",
    action = 'store_true',
    default = False)
    

args = parser.parse_known_args()[0]
print(args)

groups = [{
    'host': args.ip,
    'colBoards': args.cols,
    'rowBoards': args.rows} for _ in range(args.groups)]


# parser.add_argument(
#     "--debug", 
#     required = False,
#     action = 'store_true',
#     help     = "enable auto-polling",
# )

kwargs = {}
kwargs['simulation'] = args.sim
kwargs['emulate'] = args.emulate
kwargs['groups'] = groups
kwargs['plots'] = args.plots

print(kwargs)

with warm_tdm.WarmTdmRoot(pollEn=False, **kwargs) as root:

    # Create GUI
    appTop = pyrogue.gui.application(sys.argv)
    guiTop = pyrogue.gui.GuiTop()
    guiTop.addTree(root)
    guiTop.resize(1500,1500)

    # Run gui
    appTop.exec_()
