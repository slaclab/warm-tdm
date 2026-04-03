##
## Stream data reader
##

from collections import defaultdict

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

import os
swpath=''.join(os.path.abspath('./').partition('software')[:-1])
pyrogue.addLibraryPath(os.path.join(swpath,'python')+'/')
pyrogue.addLibraryPath(os.path.join(swpath.replace('software','firmware'),'python')+'/')
pyrogue.addLibraryPath(os.path.join(swpath.replace('software','firmware'),'submodules/surf/python')+'/')

import warm_tdm_api
import warm_tdm

nesteddict = lambda:defaultdict(nesteddict)

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)    

import pandas as pd
class StreamReader():
    def __init__(self):
        self.data = nesteddict()
        
    def readStream(self, filename):
        # clear the dictionary
        self.data = nesteddict()
        with pyrogue.utilities.fileio.FileReader(files=[filename],configChan=255) as fd:
            for header, data in fd.records():
                # metadata
                if header.channel == 9:
                    print(f"Record {fd.currCount}/{fd.totCount}")
                    print(f"  Channel = {header.channel}")
                    print(f"  Size    = {header.size}")
                    print(f"  Flags   = {header.flags:#x}")
                    print(f"  Error   = {header.error:#x}")

                    # data is a numpy array view of payload bytes
                    print(f"  First byte = {data[0]:#x}")

                    print(fd.configDict.get('root.Group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx.DaqReadoutRate'))
                # readout
                #if header.channel == 9:
                #    dr = warm_tdm.DataReadout.from_numpy(data)
                #    for s in dr.samples:
                #        if not self.data[s.col][s.row]:
                #            self.data[s.col][s.row] = []
                #    
                #        self.data[s.col][s.row].append(s.value)