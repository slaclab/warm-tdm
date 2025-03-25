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

reader = rogue.utilities.fileio.StreamReader()

ampModel = warm_tdm.FastDacAmplifierSE()

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)    

@dataclass
class PidDebugMessage:

    col: int
    row: int
    runTime: int
    baseline: int
    accumError: int
    sq1FbStart: int
    sumAccum: int
    diff: int
    pidResult: int
    fluxJumps: int
    sq1Fb: int
    accumSamples: int
    readoutCount: int
    
    @classmethod
    def from_numpy(cls, arr):
        # Word 0
        col = int(arr[0] & 0b111)
        row = int(arr[1] & 0xFF)
        runTime = unsigned_int(arr[3:8])
        # Word 1
        baseline = signed_int(arr[8:12])
        # Word 2
        accumError = signed_int(arr[16:20])
        # Word 3
        sq1FbStart = unsigned_int(arr[24:26])
        # Word 4
        sumAccum = signed_int(arr[32:36])
        # Word 5
        diff = signed_int(arr[40:44])
        # Word 6
        pidResult = signed_int(arr[48:56])
        # Word 7
        fluxJumps = signed_int(arr[56])
        # Word 8
        sq1Fb = unsigned_int(arr[64:66])
        # Word 9
        accumSamples = unsigned_int(arr[72:76])
        readoutCount = unsigned_int(arr[76:80])

        return cls(
            col = col,
            row = row,
            runTime = runTime,
            baseline = baseline,
            accumError = accumError,
            sq1FbStart = sq1FbStart,
            sumAccum = sumAccum,
            diff = diff,
            pidResult =pidResult,
            fluxJumps = fluxJumps,
            sq1FbEnd = sq1FbEnd,
            accumSamples = accumSamples,
            readoutCount = readoutCount)
        
        

class PidDebugParser(rogue.interfaces.stream.Slave):
    def __init__(self):
        super().__init__()
        #rogue.interfaces.stream.Slave.__init__(self)

        self.data = nesteddict()

    def _acceptFrame(self, frame):
        channel = frame.getChannel()
        arr = frame.getNumpy()

        # Size must be 72
        if len(arr) != 80:
            return

        msg = PidDebugMessage.from_numpy(arr)
        self.data[msg.col][msg.row]

        if not self.data[col][row]:
            self.data[msg.col][msg.row] = []
        self.data[msg.col][msg.row].append(msg)
        print(f'Got PID Debug frame for col {msg.col}, row {msg.row}, size {len(arr)}, sq1fb {msg.sq1Fb:x}')        

parser = PidDebugParser()

reader >> parser


def main(args):
    reader.open(args[1])
    reader.closeWait()

if __name__ == '__main__':
    main(sys.argv)
        
