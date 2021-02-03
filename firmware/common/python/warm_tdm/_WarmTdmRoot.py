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
            simEthPort= 7000
            ethDebug=False,
            ip='192.168.2.10',
            
            stack = [
                {'cls': warm_tdm.RowModule,
                 'simPgpPort' : 8000},
                {'cls': warm_tdm.RowModule,
                 'simPgpPort' : 8100}]

            **kwargs):

        super().__init__(**kwargs)

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(len(stack))

        pgpRing = []

        # Instantiate and link each board in the stack
        for index, board in enumerate(stack):
            # Create streams to each board
            srpStream = rogue.interfaces.stream.TcpClient('localhost', simEthPort + (0x00 | index))
            dataStream = rogue.interfaces.stream.TcpClient('localhost', simEthPort + (0x01 | index))
            prbsStream = rogue.interfaces.stream.TcpClient('localhost', simEthPort + (0x02 | index))
            loopbackStream = rogue.interfaces.stream.TcpClient('localhost', simEthPort + (0x03 | index))

            addInterfaces(srpStream, dataStream, prbsStream, loopbackStream)

            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3()
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            board['cls'](name=f'Board[{index}]', memBase=srp)            

            # Link the data stream to the DataWriter
            dataStream >> self.DataWriter.getChannel(index)

            # PRBS modules
            self.add(pyrogue.utilities.prbs.PrbsTx(name=f'PrbsTx[{index}]', stream=prbsStream))
            self.add(pyrogue.utilities.prbs.PrbsRx(name=f'PrbsRx[{index}]', stream=prbsStream))

            # Loopback
            self.add(pyrogue.utilities.prbs.PrbsTx(name=f'LoopbackTx[{index}]', stream=loopbackStream))
            self.add(pyrogue.utilities.prbs.PrbsRx(name=f'LoopbackRx[{index}]', stream=loopbackStream))

            # Connect to simulated PGP ring
            pgp = rogue.interfaces.stream.TcpClient('localhost', board['simPgpPort'])
            pgpRing.append(pgp)
            self.addInterface(pgp)

            if index /= 0:
                pgpRing[index-1] >> pgpRing[index]

            if index == len(stack):
                pgpRing[index] >> pgpRing[0]
            
