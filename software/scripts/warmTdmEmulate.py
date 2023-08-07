#!/usr/bin/env python3
import logging

import pyrogue
import pyrogue.pydm
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api

groupCount = 12

class EmulateRoot(pyrogue.Root):

    def __init__(self):
        pyrogue.Root.__init__(self, description="Emulate Root")


        dr = warm_tdm_api.TdmDataReceiver(expand=True)
        self.add(dr)

        for i in range(groupCount):
            dg = warm_tdm_api.TdmGroupEmulate(name=f'TdmGroupEmulate[{i}]', expand=True, groupId=i)
            dr << dg
            self.add(dg)

        self.add(warm_tdm_api.RunControl())

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='*', port=0)
        self.addInterface(self.zmqServer)

with EmulateRoot() as root:
    pyrogue.pydm.runPyDM(serverList=root.zmqServer.address, title='Warm TDM Emulation')


