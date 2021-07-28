#!/usr/bin/env python3

import pyrogue
import pyrogue.pydm
import rogue
from TDMSubroutines import *

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')

import warm_tdm_api

with warm_tdm_api.GroupRoot() as root:
	group = root.Group
	
	for col in range(group.NumColumns.get()):
		saTune(group,col)

	fasTune(group)

	sq1Tune(group)

	sq1RampRow(group)

	tesRampRow(group)

	#open gui
	pyrogue.pydm.runPyDM(root=root,title='TestGroup',sizeX=1000,sizeY=500)