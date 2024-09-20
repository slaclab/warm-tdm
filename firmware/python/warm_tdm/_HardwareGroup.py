
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
            colBoardClass,
            colFeClass,
            rowBoardClass,
            rowFeClass,
            dataWriter,
            simulation=False,
            emulate=False,
            host='192.168.3.11',
            colBoards=4,
            rowBoards=1,
            rows=32,
            **kwargs):

        super().__init__(**kwargs)

#        print(f'HardwareGroup with {rows} rows')

        # Open rUDP connections to the Manager board
        if simulation is False and emulate is False:
            srpUdp = pyrogue.protocols.UdpRssiPack(host=host, port=SRP_PORT, packVer=2, name='SrpRssi', groups=['NoConfig'])
            dataUdp = pyrogue.protocols.UdpRssiPack(host=host, port=DATA_PORT, packVer=2, name='DataRssi', enSsi=False, groups=['NoConfig'])
            self.add(srpUdp)
            self.add(dataUdp)
            self.addInterface(srpUdp, dataUdp)

        # Direct SRP
        COL_SIM_SRP_PORTS = [10000 + (i * 1000) for i in range(colBoards)]
        ROW_SIM_SRP_PORTS = [10000 + (i * 1000) for i in range(colBoards, colBoards+rowBoards)]        

        # Instantiate and link each board in the Group
        for index in range(colBoards):

            if emulate is True:
                srp =  pyrogue.interfaces.simulation.MemEmulate()
                dataStream = rogue.interfaces.stream.Master()

            elif simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', COL_SIM_SRP_PORTS[index])
#                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | index)*2)
                dataStream = rogue.interfaces.stream.TcpClient('localhost', SIM_DATA_PORT + (0x00 <<4 | index)*2)
                self.addInterface(srpStream, dataStream)

                
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream

            else:
                srpStream = srpUdp.application(dest=index)
                dataStream = dataUdp.application(dest=index)
                srp = rogue.protocols.srp.SrpV3()
                srp == srpStream

            # Data streams are packetized and need to be unpacked
            packetizer = rogue.protocols.packetizer.CoreV2(False, False, False);
            fifo = rogue.interfaces.stream.Fifo(10, 0, False)
            dataStream >> fifo >> packetizer.transport()
            self.addInterface(packetizer, fifo)
                

            # Instantiate the board Device tree and link it to the SRP
            self.add(colBoardClass(
                name=f'ColumnBoard[{index}]',
                frontEndClass=colFeClass,
                memBase=srp,
                expand=True,
                rows=rows))
            
            pidDebug = [warm_tdm.PidDebugger(name=f'PidDebug[{i}]', hidden=False, numRows=rows, col=i, frontEnd=self.ColumnBoard[index].AnalogFrontEnd) for i in range(8)]
            saAmps = [self.ColumnBoard[index].AnalogFrontEnd.Channel[x].SAAmp for x in range(8)]
            waveGui = warm_tdm.WaveformCaptureReceiver(hidden=False, amplifiers=saAmps)

            # Link the data stream to the DataWriter
            if emulate is False:
                dataWriterChannel = (groupId << 3) | index
                #dataStream >> dataWriter.getChannel(dataWriterChannel)


                debug = rogue.interfaces.stream.Slave()
                debug.setDebug(100, 'DataStream')
 #               dataStream >> debug
                #self.addInterface(debug)

                for i in range(8):
                    chDbg = rogue.interfaces.stream.Slave()
                    chDbg.setDebug(100, f'DataStream_App_{i}')
                    rateDrop = rogue.interfaces.stream.RateDrop(True, 0.1)
                    self.addInterface(rateDrop)
                    packetizer.application(i) >> dataWriter.getChannel(i)
                    packetizer.application(i) >> rateDrop >> pidDebug[i]                    
#                    packetizer.application(i) >> chDbg
                    #self.addInterface(chDbg, pidDebug[i])
                    
                #dataStream >> pidDebug
                packetizer.application(8) >> waveGui
#                packetizer.application(0) >> pidDebug

#                 else:
#                     debug = warm_tdm.StreamDebug()
#                     dataStream >> debug
#                     self.addInterface(debug)

        for rowIndex, boardIndex in enumerate(range(colBoards, colBoards+rowBoards)):
            # Create streams to each board
            if emulate is True:
                srp = pyrogue.interfaces.simulation.MemEmulate()

            elif simulation is True:
                srpStream = rogue.interfaces.stream.TcpClient('localhost', ROW_SIM_SRP_PORTS[rowIndex])
#                srpStream = rogue.interfaces.stream.TcpClient('localhost', SIM_SRP_PORT + (0x00 <<4 | boardIndex)*2)
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
            self.add(rowBoardClass(
                name=f'RowBoard[{rowIndex}]',
                memBase=srp,
                expand=True,
                enabled=True))

        def rl_get(read):
            #print(f'rl_get({read=})')
            length = self.ColumnBoard[0].WarmTdmCore.Timing.TimingTx.NumRows.get(read=read)
            #print(f'{length=}')
            order = self.ColumnBoard[0].WarmTdmCore.Timing.TimingTx.RowIndexOrder.get(read=read)
            #print(f'{order=}')
            #print(f'ret - {order[0:length]}')
            return order[0:length]

        def rl_set(value, write):
            tx = self.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
            tx.NumRows.set(len(value), write=write)            
            tx.RowIndexOrder.set(value=value, write=write)
#             for i,v in enumerate(value):
#                 tx.RowIndexOrder.set(value=v, index=i, write=False)
#             if write is True:
#                 tx.RowIndexOrder.write()


        if colBoards > 0:
            self.add(pyrogue.LinkVariable(
                name = 'ReadoutList',
                typeStr = 'int',
                value = [0] ,
                groups = ['NoConfig'],
                dependencies = [
                    self.ColumnBoard[0].WarmTdmCore.Timing.TimingTx.NumRows,
                    self.ColumnBoard[0].WarmTdmCore.Timing.TimingTx.RowIndexOrder],
                linkedSet = rl_set,
                linkedGet = rl_get)) #list(range(48))))

        @self.command()
        def Readout2():
            self.ReadoutList.set([0, 1])

        @self.command()
        def Readout22():
            self.ReadoutList.set(list(range(22)))

        if colBoards > 0:
            self.add(waveGui)
            for i in range(8):
                self.add(pidDebug[i])




