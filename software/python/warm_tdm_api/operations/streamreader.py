##
## Stream data reader
##

from collections import defaultdict

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

# NOTE: as a subpackage of warm_tdm_api, this module is only importable once
# warm_tdm_api itself has been imported, so warm_tdm_api / warm_tdm / surf are
# already on the library path. The previous import-time pyrogue.addLibraryPath()
# block (relative to __file__) is therefore both redundant and, after the move
# into warm_tdm_api/operations/, wrong. Path setup belongs to the entry-point
# script (e.g. warmTdmServer.py) or WARM_TDM_PATH, not to a library module.
import warm_tdm_api
import warm_tdm

nesteddict = lambda:defaultdict(nesteddict)

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)

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