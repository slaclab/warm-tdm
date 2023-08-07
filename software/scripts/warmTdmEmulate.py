#!/usr/bin/env python3
import logging

import pyrogue
import pyrogue.pydm
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api

class EmulateRoot(pyrogue.Root):

    def __init__(self):
        pyrogue.Root.__init__(self, description="Emulate Root")


        dr = warm_tdm_api.TdmDataReceiver()
        self.add(dr)

        for i in range(12):
            dg = warm_tdm_api.TdmGroupEmulate(name=f'TdmGroupEmulate[{i}]', groupId=i)
            dr << dg
            self.add(dg)

        self.add(warm_tdm_api.RunControl())

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='*', port=0)
        self.addInterface(self.zmqServer)

with EmulateRoot() as root:
    pyrogue.pydm.runPyDM(serverList=root.zmqServer.address, title='Warm TDM Emulation')


