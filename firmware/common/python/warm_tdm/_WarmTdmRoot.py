import argparse

import rogue
import pyrogue
import pyrogue.interfaces.simulation
import pyrogue.protocols
import pyrogue.utilities.fileio
import pyrogue.utilities.prbs

import warm_tdm



NORMAL_STACK = [
    {'cls': warm_tdm.ColumnModule,
     'name': 'ColumnModule[0]'},
    {'cls': warm_tdm.ColumnModule,
     'name': 'ColumnModule[1]'},
    {'cls': warm_tdm.ColumnModule,
     'name': 'ColumnModule[2]'},
    {'cls': warm_tdm.ColumnModule,
     'name': 'ColumnModule[3]'},
    {'cls': warm_tdm.RowModule,
     'name': 'RowModule[0]'},
    {'cls': warm_tdm.RowModule,
     'name': 'RowModule[1]'}]

SIM_PORTS = list(range(7000, 7051, 10))

CONFIGS = {
    'sim': {
        'stack': {
            'pollEn': False,
            'timeout': 1000,
            'host': 'localhost',
            'srpPort': 10000,
            'dataPort': 20000,
            'simPorts': SIM_PORTS,
            'stack': NORMAL_STACK},
        'row': {
            'pollEn': False,            
            'timeout': 1000,            
            'host': 'localhost',
            'srpPort': 10000,
            'dataPort': 20000,
            'simPorts': [7000],
            'stack': [{'cls': warm_tdm.RowModule, 'name': 'RowModule[0]'}]},
        'col': {
            'pollEn': False,            
            'timeout': 1000,            
            'host': 'localhost',
            'srpPort': 10000,
            'dataPort': 20000,
            'simPorts': [7000],
            'stack': [{'cls': warm_tdm.RowModule, 'name': 'RowModule[0]'}]}},
    'hw': {
        'stack': {
            'pollEn': False,
            'host': '192.168.2.11',
            'srpPort': 8192,
            'dataPort': 8193,
            'simPorts': None,
            'stack': NORMAL_STACK},
        'row': {
            'host': '192.168.2.11',
            'srpPort': 8192,
            'dataPort': 8193,
            'simPorts': None,
            'stack': [{'cls': warm_tdm.RowModule, 'name': 'RowModule[0]'}]},
        'col': {
            'host': '192.168.2.11',            
            'srpPort': 8192,
            'dataPort': 8193,
            'simPorts': None,
            'stack': [{'cls': warm_tdm.RowModule, 'name': 'RowModule[0]'}]}}}
 

class WarmTdmRoot(pyrogue.Root):
    def __init__(
            self,
            host='192.168.2.10',
            srpPort=8192,
            dataPort=8193,
            simPorts=None,
            stack=NORMAL_STACK,
            **kwargs):

        self._doHeartbeat = False
        super().__init__(**kwargs)

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(len(stack))

        pgpRing = []

#        ethPort = stack[0]['simEthSrpPort']

        # Instantiate and link each board in the stack
        for index, board in enumerate(stack):
            # Create streams to each board
            if simPorts is not None:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', srpPort + (0x00 <<4 | index)*2)
                self.addInterface(srpStream)            
            else:
                udp = pyrogue.protocols.UdpRssiPack(host=host, port=srpPort, packVer=2)
                srpStream = udp.application(dest=index)
                self.addInterface(udp)            

            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3() #board['name'])
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(board['cls'](name=board['name'], memBase=srp))

            # Link the data stream to the DataWriter
#            dataStream >> self.DataWriter.getChannel(index)

            # Connect to simulated PGP ring
            if simPorts is not None:
                pgp = pyrogue.interfaces.simulation.Pgp2bSim(vcCount=4, host='localhost', port=SIM_PORTS[index])
                pgpRing.append(pgp)
                self.addInterface(pgp) # Should modify Pgp2bSim to stop the TcpClients on _stop

        numBoards = len(pgpRing)
        for i in range(numBoards):
            print(f'Linking board {i} to board {(i+1)%numBoards}')
            pgpRing[i].vc[0] >> pgpRing[(i+1)%numBoards].vc[0]
            pgpRing[i].sb.setRecvCb(pgpRing[(i+1)%numBoards].sb.send)
            
#         pgpRing[0].vc[0] >> pgpRing[1].vc[0] >> pgpRing[2].vc[0] >> pgpRing[3].vc[0] >> pgpRing[4].vc[0] >> pgpRing[5].vc[0] >> pgpRing[0].vc[0]
#         pgpRing[0].sb.setRecvCb(pgpRing[1].sb.send)
#         pgpRing[1].sb.setRecvCb(pgpRing[2].sb.send)
#         pgpRing[2].sb.setRecvCb(pgpRing[3].sb.send)
#         pgpRing[3].sb.setRecvCb(pgpRing[4].sb.send)
#         pgpRing[4].sb.setRecvCb(pgpRing[5].sb.send)
#         pgpRing[5].sb.setRecvCb(pgpRing[0].sb.send)
        #pgpRing[0].sb.send(0, 0)

        rowModules = [x for x in self.deviceList if isinstance(x, warm_tdm.RowModule)]        
        if len(rowModules) > 0: 
            self.add(warm_tdm.RowSelectArray(rowModules))

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
#                 pgpRing[index].sb.setRecvCb(pgpRing[0].sb.send)
