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

class TdmDataReceiver(pr.Device):

    def __init__(self, **kwargs ):
        pr.Device.__init__(self, **kwargs)

        self._processor = warm_tdm_lib.TdmDataReceiver()

        self.add(pr.LocalVariable(name='FrameCount', description='Frame Count',
                                  mode='RO', value=0, pollInterval=1,
                                  localGet=lambda : self._processor.getRxFrameCount()))

        self.add(pr.LocalVariable(name='ByteCount', description='Byte Count',
                                  mode='RO', value=0, pollInterval=1,
                                  localGet=lambda : self._processor.getRxByteCount()))

    def countReset(self):
        self._processor.countReset()
        super().countReset()

    def _getStreamSlave(self):
        return self._processor

    def __lshift__(self,other):
        pr.streamConnect(other,self)
        return other

