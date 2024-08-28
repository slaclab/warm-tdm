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
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Master', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Hub', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.memory.Transaction', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Variable.RemoteVariable.GroupRoot.Group.HardwareGroup.RowBoard[0]').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#rogue.Logging.setFilter('pyrogue.packetizer', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.packetizer.Controller', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.packetizer.Application', rogue.Logging.Debug)
#rogue.Logging.setLevel(rogue.Logging.Debug)


parser = argparse.ArgumentParser()

parser.add_argument(
    "--docs",
    type     = str,
    required = False,
    default = '',
    help     = "Path To Store Docs")

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
    default = '192.168.3.11',
    help     = "IP address")

parser.add_argument(
    "--rowBoards",
    type     = int,
    default  = 1,
    help     = "Number of row boards in group")

parser.add_argument(
    "--maxRows",
    type = int,
    default = 32,
    help = "Maximum number of physical rows available")

parser.add_argument(
    "--columnBoards",
    type     = int,
    default  = 1,
    help     = "Number of column boards in group")

parser.add_argument(
    "--columnBoardType",
    choices= ['Legacy', 'FPGA'],
    default= 'Legacy')

parser.add_argument(
    "--rowBoardType",
    choices= ['Legacy', 'FPGA'],
    default= 'Legacy')

parser.add_argument(
    "--columnFrontEnd",
    choices= ['Standard', 'Ch0Feb'],
    default= 'Standard')

parser.add_argument(
    "--rowFrontEnd",
    choices= ['Standard'],
    default= 'Standard')


args = parser.parse_known_args()[0]
print(args)


colBoardDict = {
    'Legacy': warm_tdm.ColumnModule,
    'FPGA': warm_tdm.ColumnFpgaBoard}

colBoardClass = colBoardDict[args.columnBoard]

colFeDict = {
    'Standard': warm_tdm.ColumnBoardC00StandardFrontEnd,
    'Ch0Feb': warm_tdm.ColumnBoardC00FebBypassCh0}

colFeClass = colFeDict[args.columnFrontEnd]

rowBoardDict = {
    'Legacy': warm_tdm.RowModule}

rowBoardClass = rowBoardDict[args.rowBoard]

rowFeDict = {
    'Standard': warm_tdm.RowBoardC00StandardFrontEnd}

colFeClass = colFeDict[args.columnFrontEnd]
groups = [{
    'host': args.ip,
    'colBoards': args.cols,
    'rowBoards': args.rows}]

# Setup configuration
config = warm_tdm_api.GroupConfig(rowBoards=groups[0]['rowBoards'],
                                  columnBoards=groups[0]['colBoards'],
                                  host=groups[0]['host'],
                                  rowOrder=None)

with warm_tdm_api.GroupRoot(
        colBoardClass=colBoardClass,
        colFeClass=colFeClass,
        rowBoardClass=rowBoardClass,
        rowFeClass=rowFeClass,
        groupConfig=config,
        simulation=args.sim,
        emulate=args.emulate,
        numRows=args.maxRows,
        initRead=not args.sim) as root:

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


