#-----------------------------------------------------------------------------
# Title      : Warm TDM Data Receiver
#-----------------------------------------------------------------------------
# Description:
# Receive warm tmd data and hand off to daq
#-----------------------------------------------------------------------------
# This file is part of the warm tdm software platform. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the warm tdm software platform, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------
import pyrogue as pr
import warm_tdm_lib

class TdmGroupEmulate(pr.Device):

    def __init__(self, *, groupId, **kwargs ):
        pr.Device.__init__(self, **kwargs)

        self._processor = warm_tdm_lib.TdmGroupEmulate(groupId)

        self.add(pr.LocalVariable(name='FrameCount', description='Frame Count',
                                  mode='RO', value=0, pollInterval=1,
                                  localGet=lambda : self._processor.getTxFrameCount()))

        self.add(pr.LocalVariable(name='ByteCount', description='Byte Count',
                                  mode='RO', value=0, pollInterval=1,
                                  localGet=lambda : self._processor.getTxByteCount()))

        self.add(pr.LocalVariable(name='NumColBoards', description='Number Of Column Boards', mode='RW',
                                  value=4,
                                  localGet=lambda : self._processor.getNumColBoards(),
                                  localSet=lambda value: self._processor.setNumColBoards(value)))

        self.add(pr.LocalVariable(name='NumRows', description='Number Of Rows', mode='RW',
                                  value=32,
                                  localGet=lambda : self._processor.getNumRows(),
                                  localSet=lambda value: self._processor.setNumRows(value)))

    def _start(self):
        self._processor._start()

    def _stop(self):
        self._processor._stop()

    def countReset(self):
        self._processor.countReset()
        super().countReset()

    def _request(self, arg):
        tsA = arg & 0xFFFFFFFF
        tsB = (arg >> 32) & 0xFFFFFFFF
        tsC = (arg >> 64) & 0xFFFFFFFF
        self._processor.reqFrames(tsA, tsB, tsC)

    def _getStreamMaster(self):
        return self._processor

    def __rshift__(self,other):
        pr.streamConnect(self,other)
        return other

