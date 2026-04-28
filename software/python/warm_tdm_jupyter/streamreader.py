##
## Stream data reader
##

from collections import defaultdict

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

import os
_env_swpath = os.environ.get('WARM_TDM_PATH')
if _env_swpath:
    swpath = os.path.abspath(_env_swpath)
else:
    swpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_firmware_path = os.path.join(os.path.dirname(swpath), 'firmware')
pyrogue.addLibraryPath(os.path.join(swpath, 'python') + '/')
pyrogue.addLibraryPath(os.path.join(_firmware_path, 'python') + '/')
pyrogue.addLibraryPath(os.path.join(_firmware_path, 'submodules', 'surf', 'python') + '/')

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
        #with pyrogue.utilities.fileio.FileReader(files=[filename],configChan=255) as fd:
        with pyrogue.utilities.fileio.FileReader(files=[filename]) as fd:
            for header, data in fd.records():
                ## metadata
                #if header.channel == 9:
                #    if fd.configDict!={}:
                #        print(fd.configDict)
                # readout
                if header.channel == 9:
                    dr = warm_tdm.DataReadout.from_numpy(data)
                    for s in dr.samples:
                        if not self.data[s.col][s.row]:
                            self.data[s.col][s.row] = []
                    
                        self.data[s.col][s.row].append(s.value)