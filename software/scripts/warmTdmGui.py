#!/usr/bin/env python3

import pyrogue
import pyrogue.pydm
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api

from warm_tdm_api import PhysicalMap as pm

# Setup configuration
columnBoards = 4
columnChannels = 8
rowBoards = 2
rowChannels = 32

columnMap = [pm(i,j) for j in range(columnChannels) for i in range(columnBoards)]
rowMap = [pm(i,j) for j in range(rowChannels) for i in range(rowBoards)]

config = warm_tdm_api.GroupConfig(columnMap=columnMap,
                                  columnEnable=[True] * len(columnMap),
                                  rowMap=rowMap,
                                  rowOrder=[i for i in range(len(rowMap))],
                                  host='192.168.3.11',
                                  columnBoards=columnBoards,
                                  rowBoards=rowBoards)

#print(config)

with warm_tdm_api.GroupRoot(groupConfig=config, emulate=True) as root:

    pyrogue.pydm.runPyDM(root=root,title='Warm TDM',sizeX=1000,sizeY=800,ui=warm_tdm_api.pydmUi)

