#!/usr/bin/env python3

import rogue
import pyrogue.gui
import sys
import argparse
import os
import logging

if '--local' in sys.argv:
    baseDir = os.path.dirname(os.path.realpath(__file__))
    print(f'{baseDir}/../../firmware/common/python')
    pyrogue.addLibraryPath(f'{baseDir}/../../firmware/common/python')
    pyrogue.addLibraryPath(f'{baseDir}/../../firmware/submodules/surf/python')


import warm_tdm

#rogue.Logging.setFilter('pyrogue.batcher', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)

rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
logging.getLogger('pyrogue.SideBandSim').setLevel(logging.DEBUG)

# Set the argument parser
parser = argparse.ArgumentParser()

parser.add_argument(
    "--ip",
    type     = str,
    required = False,
    default = '192.168.2.10',
    help     = "IP address")

parser.add_argument(
    "--serverPort",
    type = int,
    default = 0,
    help = "ZMQ Server Port")

parser.add_argument(
    "--hwEmu",
    required = False,
    action = 'store_true',
    help     = "hardware emulation (false=normal operation, true=emulation)")

parser.add_argument(
    "--sim",
    required = False,
    action   = 'store_true',
    help     = "hardware emulation (false=normal operation, true=emulation)")

parser.add_argument(
    "--pollEn",
    required = False,
    action   = 'store_true',
    help     = "enable auto-polling")



# parser.add_argument(
#     "--debug", 
#     required = False,
#     action = 'store_true',
#     help     = "enable auto-polling",
# )

args = parser.parse_known_args()[0]
print(args)

with warm_tdm.WarmTdmRoot(timeout=1000, **vars(args)) as root:

    # Create GUI
    appTop = pyrogue.gui.application(sys.argv)
    guiTop = pyrogue.gui.GuiTop()
    guiTop.addTree(root)
    guiTop.resize(1000,1000)

    # Run gui
    appTop.exec_()
