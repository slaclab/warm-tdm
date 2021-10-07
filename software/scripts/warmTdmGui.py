#!/usr/bin/env python3
import argparse

import pyrogue
import pyrogue.pydm
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api

from warm_tdm_api import PhysicalMap as pm

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

args = parser.parse_known_args()[0]
print(args)

groups = [{
    'host': args.ip,
    'colBoards': args.cols,
    'rowBoards': args.rows}]

# Setup configuration
columnBoards = groups[0]['colBoards']
columnChannels = 8
rowBoards = groups[0]['rowBoards']
rowChannels = 32

columnMap = [pm(i,j) for j in range(columnChannels) for i in range(columnBoards)]
rowMap = [pm(i,j) for j in range(rowChannels) for i in range(rowBoards)]

config = warm_tdm_api.GroupConfig(columnMap=columnMap,
                                  columnEnable=[True] * len(columnMap),
                                  rowMap=rowMap,
                                  rowOrder=[i for i in range(len(rowMap))],
                                  host=groups[0]['host'],
                                  columnBoards=columnBoards,
                                  rowBoards=rowBoards)

#print(config)

with warm_tdm_api.GroupRoot(groupConfig=config, simulation=args.sim, emulate=args.emulate) as root:

    pyrogue.pydm.runPyDM(root=root,title='Warm TDM',sizeX=2000,sizeY=2000,ui=warm_tdm_api.pydmUi)

