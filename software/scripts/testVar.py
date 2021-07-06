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
	
	group.SaFb[0].set(3.0)
	
	#saTune(group)

	fasTune(group)

	sq1Tune(group)

	sq1RampRow(group)

	tesRampRow(group)

	#open gui
	pyrogue.pydm.runPyDM(root=root,title='TestGroup',sizeX=1000,sizeY=500)
