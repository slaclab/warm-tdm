
import rogue
import pyrogue
import pyrogue.interfaces.simulation
import pyrogue.protocols
import pyrogue.utilities.fileio

import warm_tdm

SIM_SRP_PORT = 10000
SIM_DATA_PORT = 20000

SRP_PORT = 8192
DATA_PORT = 8193

class HardwareGroup(pyrogue.Device):

    
    def __init__(
            self,
            simulation=False,
            host='192.168.3.11',
            colBoards=4,
            rowBoards=2,
            **kwargs):

        super().__init__(**kwargs)

        # Open rUDP connections to the Manager board
        if simulation is False:
            srpUdp = pyrogue.protocols.UdpRssiPack(host=host, port=SRP_PORT, packVer=2)
            dataUdp = pyrogue.protocols.UdpRssiPack(host=host, port=DATA_PORT, packVer=2)            
            self.add(srpUdp)
            #self.add(dataUdp)                        
            self.addInterface(srpUdp, dataUdp)

                
        # Instantiate and link each board in the Group
        for index in range(colBoards):
            # Create streams to each board
            if simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | index)*2)
                dataStream = rogue.interfaces.stream.TcpClient('localhost', SIM_DATA_PORT + (0x00 <<4 | index)*2)
                self.addInterface(srpStream, dataStream)            
            else:
                srpStream = srpUdp.application(dest=index)
                dataStream = dataUdp.application(dest=index)


            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3() #board['name'])
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(warm_tdm.ColumnModule(name=f'ColumnBoard[{index}]', memBase=srp))

            # Link the data stream to the DataWriter
            debug = warm_tdm.StreamDebug()
            dataStream >> debug
            self.addInterface(debug)

        for rowIndex, boardIndex in enumerate(range(colBoards, colBoards+rowBoards)):
            # Create streams to each board
            if simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | boardIndex)*2)
                dataStream = rogue.interfaces.stream.TcpClient('localhost', SIM_DATA_PORT + (0x00 <<4 | boardIndex)*2)
                self.addInterface(srpStream, dataStream)            
            else:
                srpStream = srpUdp.application(dest=boardIndex)
                dataStream = dataUdp.application(dest=boardIndex)

            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3() #board['name'])
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(warm_tdm.RowModule(name=f'RowBoard[{rowIndex}]', memBase=srp))

        self.add(pyrogue.LocalVariable(
            name = 'ReadoutList',
            typeStr = 'int',
            value = [0, 1 , 2, 3]))

        self.add(warm_tdm.RowSelectArray(
            rowModules = [self.RowBoard[i] for i in range(rowBoards)]))


    def writeBlocks(self, **kwargs):
        # Do the normal write
        super().writeBlocks(**kwargs)

        #Then configure the row selects according to the ReadoutList
        self.RowSelectArray.configure(self.ReadoutList.value())
            

