
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
            groupId = 0,
            simulation=False,
            host='192.168.3.11',
            colBoards=4,
            rowBoards=2,
            plots=False,
            **kwargs):

        super().__init__(**kwargs)

        # Open rUDP connections to the Manager board
        if simulation is False:
            srpUdp = pyrogue.protocols.UdpRssiPack(host=host, port=SRP_PORT, packVer=2, name='SrpRssi')
            dataUdp = pyrogue.protocols.UdpRssiPack(host=host, port=DATA_PORT, packVer=2, name='DataRssi')            
            self.add(srpUdp)
            self.add(dataUdp)                        
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

#                 srpLoopDest = srpUdp.application(dest = 0x10)
#                 dataLoopDest = dataUdp.application(dest = 0x10)
#                 m = [rogue.interfaces.stream.Master() for x in range(2)]
#                 s = [rogue.interfaces.stream.Slave() for x in range(2)]

#                 for x in range(2):
#                     s[x].setDebug(10, f'LoopDebug{x}')
# #                    m[x].setDebug(10, f'LoopDebug{x}')
                    
#                 m[0] >> srpLoopDest >> s[0]
#                 m[1] >> dataLoopDest >> s[1]

#                 @self.command(name=f'LoopFrame{index}')
#                 def _():
#                     for y in range(2):
#                         frame = m[y]._reqFrame(50000, True)
#                         ba = bytearray((i%256 for i in range(32000)))
#                         self._log.debug(f'Sending loopback frame {ba} for {y}')
#                         frame.write(ba, 0)
#                         m[y]._sendFrame(frame)
                


            # Create SRP and link to SRP stream
            srp = rogue.protocols.srp.SrpV3() #board['name'])
            srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(warm_tdm.ColumnModule(name=f'ColumnBoard[{index}]', memBase=srp, expand=True))

            # Link the data stream to the DataWriter
            dataWriterChannel = (groupId << 3) | index
            dataStream >> self.root.DataWriter.getChannel(dataWriterChannel)
            
            #debug = warm_tdm.StreamDebug()
            if plots:
                plotter = warm_tdm.Scope()
                dataStream >> plotter
                self.addInterface(plotter)

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
            self.add(warm_tdm.RowModule(name=f'RowBoard[{rowIndex}]', memBase=srp, expand=True))

        self.add(pyrogue.LocalVariable(
            name = 'ReadoutList',
            typeStr = 'int',
            value = [0,1,2,3] )) #list(range(48))))

        self.add(warm_tdm.RowSelectArray(
            rowModules = [self.RowBoard[i] for i in range(rowBoards)]))


    def writeBlocks(self, **kwargs):
        # Do the normal write
        super().writeBlocks(**kwargs)

        #Then configure the row selects according to the ReadoutList
        self.RowSelectArray.configure(self.ReadoutList.value())
            

