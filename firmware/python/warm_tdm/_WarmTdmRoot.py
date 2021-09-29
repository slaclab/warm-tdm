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

# CONFIGS = {
#     'sim': {
#         'group': {
#             'groups': [{
#                 'host': 'localhost',
#                 'colBoards': 4,
#                 'rowBoards': 2}]},
#         'row': {
#             'groups': [{
#                 'host': 'localhost',
#                 'colBoards': 0,
#                 'rowBoards': 1}],
#         'col': {
#             'groups': [{
#                 'host': 'localhost',
#                 'colBoards': 0,
#                 'rowBoards': 1}],
#     'hw': {
#         'group': {
#             'groups': [NORMAL_GROUP]},
#         'test': {
#             'groups': [{
#                 'host': '192.168.3.11',
#                 'colBoards': 3,
#                 'rowBoards': 2

#         'row': {
#             'pollEn': False,
#             'host': '192.168.3.12',
#             'srpPort': 8192,
#             'dataPort': 8193,
#             'group': [{'cls': warm_tdm.RowModule, 'name': 'RowModule[0]'}]},
#         'col': {

#             'host': '192.168.3.11',
#             'srpPort': 8192,
#             'dataPort': 8193,
#             'simPorts': None,
#             'group': [{'cls': warm_tdm.ColumnModule, 'name': 'ColumnModule[0]'}]}}}

class StreamDebug(rogue.interfaces.stream.Slave):
    def __init__(self, ):
        rogue.interfaces.stream.Slave.__init__(self)

    def _conv(self, adc):
        return (adc//4)/2**13

    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        ba = bytearray(frame.getPayload())
        frame.read(ba, 0)
        numBytes = len(ba)
        print(f'Got Frame on channel {frame.getChannel()}: {numBytes} bytes')
        adcs = np.frombuffer(ba, dtype=np.int16)
        voltages = np.array([self._conv(adc) for adc in adcs], dtype=np.float64)
        adcs.resize(numBytes//16, 8)
        voltages.resize(numBytes//16, 8)        
        print(adcs)
        print(voltages)        

        means = [np.mean(voltages[:,i]) for i in range(8)]
        print(f'Mean: {means}')
        noises = [np.std(adcs[:,i]) for i in range(8)]
        print(f'Noise: {noises}')

class WarmTdmRoot(pyrogue.Root):
    def __init__(
            self,
            simulation=False,
            plots=False,
            groups=[NORMAL_GROUP],
            **kwargs):

        # Disable polling and set a longer timeout in simulation mode
        if simulation:
            kwargs['pollEn'] = False
            kwargs['timeout'] = 1000

        #self._doHeartbeat = False
        super().__init__(**kwargs)

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(len(groups))

        for i, s in enumerate(groups):
            self.add(warm_tdm.HardwareGroup(groupId=i, dataWriter=self.DataWriter, simulation=simulation, expand=True, plots=plots, **s))














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
