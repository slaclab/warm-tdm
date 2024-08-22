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
            host,
            rowBoards,
            colBoards,
            frontEndClass,            
            simulation=False,
            emulate=False,
            plots=False,

            **kwargs):

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
            rows=32,
            frontEndClass=frontEndClass,
            dataWriter=self.DataWriter,
            simulation=simulation,
            emulate=emulate,
            host=host,
            colBoards=colBoards,
            rowBoards=rowBoards,
            plots=plots,
#            groups=['Hardware'],
            expand=True))















        # Add the data writer
#            dataStream >> self.DataWriter.getChannel(index)

            # Connect to simulated PGP ring
#             if simPorts is not None:
#                 pgp = pyrogue.interfaces.simulation.Pgp2bSim(vcCount=4, host='localhost', port=SIM_PORTS[index])
#                 pgpRing.append(pgp)
#                 self.addInterface(pgp) # Should modify Pgp2bSim to stop the TcpClients on _stop

#         numBoards = len(pgpRing)
#         for i in range(numBoards):
#             print(f'Linking board {i} to board {(i+1)%numBoards}')
#             pgpRing[i].vc[0] >> pgpRing[(i+1)%numBoards].vc[0]
#             pgpRing[i].sb.setRecvCb(pgpRing[(i+1)%numBoards].sb.send)

#         pgpRing[0].vc[0] >> pgpRing[1].vc[0] >> pgpRing[2].vc[0] >> pgpRing[3].vc[0] >> pgpRing[4].vc[0] >> pgpRing[5].vc[0] >> pgpRing[0].vc[0]
#         pgpRing[0].sb.setRecvCb(pgpRing[1].sb.send)
#         pgpRing[1].sb.setRecvCb(pgpRing[2].sb.send)
#         pgpRing[2].sb.setRecvCb(pgpRing[3].sb.send)
#         pgpRing[3].sb.setRecvCb(pgpRing[4].sb.send)
#         pgpRing[4].sb.setRecvCb(pgpRing[5].sb.send)
#         pgpRing[5].sb.setRecvCb(pgpRing[0].sb.send)
        #pgpRing[0].sb.send(0, 0)

#         rowModules = [x for x in self.deviceList if isinstance(x, warm_tdm.RowModule)]
#         if len(rowModules) > 0:
#             self.add(warm_tdm.RowSelectArray(rowModules, enabled=False))

#             if index != 0:
#                 for ch in range(4):
#                     pgpRing[0].vc[ch] >> pgpRing[1].vc[ch]
#                     pgpRing[index-1].vc[ch] >> pgpRing[index].vc[ch]

#                 print(f'Linking index {index-1} to index {index}')
#                 pgpRing[index-1].sb.setRecvCb(pgpRing[index].sb.send)


#             if index == len(stack)-1:
#                 for vc in range(4):
#                     pgpRing[index].vc[ch] >> pgpRing[0].vc[ch]

#                 print(f'Linking index {index} to index 0')
#                 pgpRing[index].sb.setRecvCb(pgpRi
