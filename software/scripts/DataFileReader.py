import sys

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api
import warm_tdm

nesteddict = lambda:defaultdict(nesteddict)

reader = rogue.utilities.fileio.StreamReader()

ampModel = warm_tdm.FastDacAmplifierSE()

def main(args):
    with pyrogue.utilities.fileio.FileReader(files=args) as fd:

        for header, data in fd.records():
            if header.channel == 9:
                dr = warm_tdm.DataReadout.from_numpy(data)
                print(dr)
                
            input('')

if __name__ == '__main__':
    main(sys.argv)
        
