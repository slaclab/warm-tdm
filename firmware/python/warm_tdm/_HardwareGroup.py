
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
            groupId,
            dataWriter,
            simulation=False,
            emulate=False,
            host='192.168.3.11',
            colBoards=4,
            rowBoards=2,
            rows=64,
            plots=False,
            **kwargs):

        super().__init__(**kwargs)

        print(f'HardwareGroup with {rows} rows')

        # Open rUDP connections to the Manager board
        if simulation is False and emulate is False:
            srpUdp = pyrogue.protocols.UdpRssiPack(host=host, port=SRP_PORT, packVer=2, name='SrpRssi')
            dataUdp = pyrogue.protocols.UdpRssiPack(host=host, port=DATA_PORT, packVer=2, name='DataRssi', enSsi=False)
            self.add(srpUdp)
            self.add(dataUdp)
            self.addInterface(srpUdp, dataUdp)



        # Instantiate and link each board in the Group
        for index in range(colBoards):

            if emulate is True:
                srp =  pyrogue.interfaces.simulation.MemEmulate()

            elif simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | index)*2)
                dataStream = rogue.interfaces.stream.TcpClient('localhost', SIM_DATA_PORT + (0x00 <<4 | index)*2)
                self.addInterface(srpStream, dataStream)            
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream

            else:
                srpStream = srpUdp.application(dest=index)
                dataStream = dataUdp.application(dest=index)
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream

            # Instantiate the board Device tree and link it to the SRP
            self.add(warm_tdm.ColumnModule(name=f'ColumnBoard[{index}]', memBase=srp, expand=True, rows=rows, waveform_stream=dataStream))
            waveGui = warm_tdm.WaveformCaptureReceiver(hidden=True, live_plots=plots)                        

            # Link the data stream to the DataWriter
            if emulate is False:
                dataWriterChannel = (groupId << 3) | index
                dataStream >> dataWriter.getChannel(dataWriterChannel)
            
                #debug = warm_tdm.StreamDebug()

                dataStream >> waveGui

#                 else:
#                     debug = warm_tdm.StreamDebug()
#                     dataStream >> debug
#                     self.addInterface(debug)

        for rowIndex, boardIndex in enumerate(range(colBoards, colBoards+rowBoards)):
            # Create streams to each board
            if emulate is True:
                srp = pyrogue.interfaces.simulation.MemEmulate()

            elif simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | boardIndex)*2)
                dataStream = rogue.interfaces.stream.TcpClient('localhost', SIM_DATA_PORT + (0x00 <<4 | boardIndex)*2)
                self.addInterface(srpStream, dataStream)            
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream

            else:
                srpStream = srpUdp.application(dest=boardIndex)
                dataStream = dataUdp.application(dest=boardIndex)
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream
            
            # Instantiate the board Device tree and link it to the SRP
            self.add(warm_tdm.RowModule(name=f'RowBoard[{rowIndex}]', memBase=srp, expand=True))

        self.add(pyrogue.LocalVariable(
            name = 'ReadoutList',
            typeStr = 'int',
            value = [0,1,2,3] )) #list(range(48))))

        self.add(waveGui)


    def writeBlocks(self, **kwargs):
        # Do the normal write
        super().writeBlocks(**kwargs)

        #Then configure the row selects according to the ReadoutList
        self.RowSelectArray.configure(self.ReadoutList.value())


