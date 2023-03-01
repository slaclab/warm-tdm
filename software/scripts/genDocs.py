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

groups = [{
    'host': '127.0.0.1',
    'colBoards': 1,
    'rowBoards': 1}]

# Setup configuration
config = warm_tdm_api.GroupConfig(rowBoards=groups[0]['rowBoards'],
                                  columnBoards=groups[0]['colBoards'],
                                  host=groups[0]['host'],
                                  rowOrder=None)

with warm_tdm_api.GroupRoot(groupConfig=config, simulation=False, emulate=True, plots=False) as root:

    root.genDocuments(path="../../docs/src/generated/",incGroups=['DocApi'],excGroups=['NoDoc','Enable','Hardware'])

