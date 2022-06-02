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

#rogue.Logging.setFilter('pyrogue.memory.block', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Variable').setLevel(logging.DEBUG)

parser = argparse.ArgumentParser()

parser.add_argument(
    "--server",
    type     = str,
    required = False,
    default = 'localhost:9099')

args = parser.parse_known_args()[0]

pyrogue.pydm.runPyDM(serverList=args.server,title='Warm TDM',sizeX=2000,sizeY=2000,ui=warm_tdm_api.pydmUi)

pyrogue.waitCntrlC()
