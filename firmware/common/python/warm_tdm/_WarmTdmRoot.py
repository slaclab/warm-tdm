import argparse

import rogue
import pyrogue
import pyrogue.interfaces.simulation
import pyrogue.protocols
import pyrogue.utilities.fileio
import pyrogue.utilities.prbs

import warm_tdm

class WarmTdmRoot(pyrogue.Root):
    def __init__(
            self,
            hwEmu=False,
            sim=False,
            ethDebug=False,
            ip='192.168.2.10',
            stack = [
                {'cls': warm_tdm.ColumnModule,
                 'simEthSrpPort' : 10000,
                 'simPgpPort' : 7000},
                {'cls': warm_tdm.ColumnModule,
                 'simEthSrpPort' : 10000 + 1000,
                 'simPgpPort' : 7000 + 10},
                {'cls': warm_tdm.ColumnModule,
                 'simEthSrpPort' : 10000 + 2000,
                 'simPgpPort' : 7000 + 20},
                {'cls': warm_tdm.ColumnModule,
                 'simEthSrpPort' : 10000 + 3000,
                 'simPgpPort' : 7000 + 30},
                {'cls': warm_tdm.RowModule,
                 'simEthSrpPort' : 10000 + 4000,
                 'simPgpPort' : 7000 + 40},
                {'cls': warm_tdm.RowModule,
                 'simEthSrpPort' : 10000 + 5000,
                 'simPgpPort' : 7000 + 50}],
            **kwargs):

        super().__init__(**kwargs)

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(len(stack))

        pgpRing = []

        ethPort = stack[0]['simEthSrpPort']

        # Instantiate and link each board in the stack
        for index, board in enumerate(stack):
            # Create streams to each board
            srpStream = rogue.interfaces.stream.TcpClient('localhost', ethPort + (0x00 <<4 | index)*2)

            self.addInterface(srpStream)

            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3()
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(board['cls'](name=f'Board[{index}]', memBase=srp))

            # Link the data stream to the DataWriter
#            dataStream >> self.DataWriter.getChannel(index)

            # Connect to simulated PGP ring
            pgp = pyrogue.interfaces.simulation.Pgp2bSim(vcCount=4, host='localhost', port=board['simPgpPort'])
            
            pgpRing.append(pgp)
            self.addInterface(pgp) # Should modify Pgp2bSim to stop the TcpClients on _stop

        pgpRing[0].vc[0] >> pgpRing[1].vc[0] >> pgpRing[2].vc[0] >> pgpRing[3].vc[0] >> pgpRing[4].vc[0] >> pgpRing[5].vc[0] >> pgpRing[0].vc[0]
        pgpRing[0].sb.setRecvCb(pgpRing[1].sb.send)
        pgpRing[1].sb.setRecvCb(pgpRing[2].sb.send)
        pgpRing[2].sb.setRecvCb(pgpRing[3].sb.send)
        pgpRing[3].sb.setRecvCb(pgpRing[4].sb.send)
        pgpRing[4].sb.setRecvCb(pgpRing[5].sb.send)        
        pgpRing[5].sb.setRecvCb(pgpRing[0].sb.send)
        #pgpRing[0].sb.send(0, 0)
            
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
                    
