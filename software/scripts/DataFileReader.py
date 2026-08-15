import sys
from collections import defaultdict

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api
import warm_tdm

nesteddict = lambda:defaultdict(nesteddict)

datadict = nesteddict()
def main(args):
    with pyrogue.utilities.fileio.FileReader(files=args) as fd:

        for header, data in fd.records():
            if header.channel == 9:
                dr = warm_tdm.DataReadout.from_numpy(data)
                for s in dr.samples:
                    #print(s)
                    if not datadict[s.col][s.row]:
                        datadict[s.col][s.row] = []

                    datadict[s.col][s.row].append(s.value)
                

if __name__ == '__main__':
    main(sys.argv)
        
