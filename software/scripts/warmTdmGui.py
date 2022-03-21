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

from warm_tdm_api import PhysicalMap as pm

#rogue.Logging.setFilter('pyrogue.memory.block', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Master', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Hub', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Transaction', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Variable').setLevel(logging.DEBUG)

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

parser.add_argument(
    "--docs",
    type     = str,
    required = False,
    default = '',
    help     = "Path To Store Docs")


args = parser.parse_known_args()[0]
print(args)

groups = [{
    'host': args.ip,
    'colBoards': args.cols,
    'rowBoards': args.rows}]

# Setup configuration
config = warm_tdm_api.GroupConfig(rowBoards=groups[0]['rowBoards'],
                                  columnBoards=groups[0]['colBoards'],
                                  host=groups[0]['host'],
                                  rowOrder=None)

# root = warm_tdm_api.GroupRoot(groupConfig=config, simulation=args.sim, emulate=args.emulate, plots=args.plots)
# root.start()
# #pyrogue.waitCntrlC()

with warm_tdm_api.GroupRoot(groupConfig=config, simulation=args.sim, emulate=args.emulate, plots=args.plots) as root:

    if args.docs != '':
        root.genDocuments(path=args.docs,incGroups=['DocApi'],excGroups=['NoDoc','Enable','Hardware'])

    pyrogue.pydm.runPyDM(root=root,title='Warm TDM',sizeX=2000,sizeY=2000,ui=warm_tdm_api.pydmUi)

    pyrogue.waitCntrlC()
