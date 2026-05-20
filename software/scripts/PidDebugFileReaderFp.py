#-----------------------------------------------------------------------------
# This file is part of the 'warm-tdm' project. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'warm-tdm' project, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

from collections import defaultdict
import sys
import numpy as np

import rogue.interfaces.stream
import rogue.utilities.fileio

nesteddict = lambda: defaultdict(nesteddict)

PidDebugFpType = np.dtype([
    # Word 0
    ('col', np.uint8),
    ('row', np.uint8),
    ('runTimeLow', np.uint16),
    ('runTimeHigh', np.uint32),
    # Word 1
    ('accumErrorFp', np.float32),
    ('sq1FbFullFp', np.float32),
    # Word 2
    ('sumAccumFp', np.float32),
    ('newSumAccum', np.float32),
    # Word 3
    ('sq1FbNewFp', np.float32),
    ('numFluxJumps', np.int32),
    # Word 4
    ('sq1FbInt', np.uint16),
    ('accumSamples', np.uint8),
    ('pad4', np.uint8),
    ('dropCount', np.uint32),
])


class PidDebugParserFp(rogue.interfaces.stream.Slave):
    def __init__(self):
        super().__init__()
        self.data = nesteddict()

    def _acceptFrame(self, frame):
        arr = frame.getNumpy()

        # Frame size must be 40 bytes
        if len(arr) != 40:
            return

        msg = arr.view(PidDebugFpType)

        col = int(msg['col'][0]) & 0b111
        row = int(msg['row'][0]) & 0xFF

        if not self.data[col][row]:
            self.data[col][row] = {
                'sq1FbNew': [],
                'accumError': [],
                'sumAccum': [],
                'numFluxJumps': [],
                'sq1FbInt': [],
            }

        self.data[col][row]['sq1FbNew'].append(float(msg['sq1FbNewFp'][0]))
        self.data[col][row]['accumError'].append(float(msg['accumErrorFp'][0]))
        self.data[col][row]['sumAccum'].append(float(msg['sumAccumFp'][0]))
        self.data[col][row]['numFluxJumps'].append(int(msg['numFluxJumps'][0]))
        self.data[col][row]['sq1FbInt'].append(int(msg['sq1FbInt'][0]))


def main(args):
    reader = rogue.utilities.fileio.StreamReader()
    parser = PidDebugParserFp()

    reader >> parser

    reader.open(args[1])
    reader.closeWait()

    return parser.data


if __name__ == '__main__':
    data = main(sys.argv)
