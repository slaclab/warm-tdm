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

	print(group.SaBiasLowOffset.get())
	group.SaBiasLowOffset.set(23)
	print(group.SaBiasLowOffset.get())
	print(group.Sq1Bias)
	print("passed these tests")
	#saTune(group)

	fasTune(group)

	sq1Tune(group)

	sq1RampRow(group)

	tesRampRow(group)

	#open gui
	pyrogue.pydm.runPyDM(root=root,title='TestGroup',sizeX=1000,sizeY=500)