from collections import defaultdict
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

data = nesteddict()
reader = rogue.utilities.fileio.StreamReader()

ampModel = warm_tdm.FastDacAmplifierSE()

class PidDebugParser(rogue.interfaces.stream.Slave):
    def __init__(self):
        super().__init__()
        #rogue.interfaces.stream.Slave.__init__(self)

        self.data = nesteddict()

    def _acceptFrame(self, frame):
        channel = frame.getChannel()
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)



        # Size must be 72
        if fl != 72:
            return

        col = raw[0] & 0b111
        row = raw[1] & 0xFF
        sq1fb_int = int.from_bytes(raw[64:66], 'little', signed=False)
        if not self.data[col][row]:
            self.data[col][row] = []
        self.data[col][row].append(sq1fb_int)
        print(f'Got PID Debug frame for col {col}, row {row}, size {fl}, sq1fb {sq1fb_int:x}')        

parser = PidDebugParser()

reader >> parser


def main(args):
    reader.open(args[1])
    reader.closeWait()

if __name__ == '__main__':
    main(sys.argv)
        
