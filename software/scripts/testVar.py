#!/usr/bin/env python3

import pyrogue
import pyrogue.pydm
import rogue
import TDMSubroutines

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')

import warm_tdm_api

with warm_tdm_api.GroupRoot() as root:
	root.group.numrows.set(3)
	rows = root.group.numrows.get()
	pyrogue.pydm.runPyDM(root=root,title='TestGroup',sizeX=1000,sizeY=500)
