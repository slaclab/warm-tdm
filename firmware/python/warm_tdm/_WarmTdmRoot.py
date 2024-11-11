import argparse
import numpy as np

import rogue
import pyrogue
import pyrogue.interfaces.simulation
import pyrogue.protocols
import pyrogue.utilities.fileio
import pyrogue.utilities.prbs

import warm_tdm

NORMAL_GROUP =  {
    'host': '192.168.3.11',
    'colBoards': 4,
    'rowBoards': 2}


class StreamDebug(rogue.interfaces.stream.Slave):
    def __init__(self, ):
        rogue.interfaces.stream.Slave.__init__(self)

    def _conv(self, adc):
        return (adc//4)/2**13

    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        data = frame.getNumpy(0, frame.getPayload())
        numBytes = data.size
        print(f'Got Frame on channel {frame.getChannel()}: {numBytes} bytes')
        frame = data.copy()
        adcs = frame.view(np.int16)
        adcs.resize(adcs.size//8, 8)
        print(adcs)

class WarmTdmRoot(pyrogue.Root):
    def __init__(
            self,
            colBoardClass,
            colFeClass,
            rowBoardClass,
            rowFeClass,
            simulation=False,
            emulate=False,
            host='192.168.3.11',
            colBoards=4,
            rowBoards=1,
            numRows=32,
            **kwargs):

        if 'groupConfig' in kwargs:
            del kwargs['groupConfig']

        # Disable polling and set a longer timeout in simulation mode
        if simulation:
            kwargs['pollEn'] = False
            kwargs['timeout'] = 1000

        #self._doHeartbeat = False
        super().__init__(**kwargs)

        self.zmqServer = pyrogue.interfaces.ZmqServer(root=self, addr='127.0.0.1', port=0)
        self.addInterface(self.zmqServer)
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter',groups='DocApi'))

        # Add the data writer
        #self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        #self >> self.DataWriter.getChannel(len(groups))

        self.add(warm_tdm.HardwareGroup(
            groupId=0,
            dataWriter=self.DataWriter,
            simulation=simulation,
            emulate=emulate,
            host=host,
            colBoards=colBoards,
            colBoardClass=colBoardClass,
            colFeClass=colFeClass,
            rowBoards=rowBoards,
            rowBoardClass=rowBoardClass,
            rowFeClass=rowFeClass,
            rows=numRows,
            groups=['Hardware'],
            expand=True))
