
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

class DataDebug(rogue.interfaces.stream.Slave):

    def _acceptFrame(self, frame):
        arr = frame.getNumpy()

        dr = warm_tdm.DataReadout.from_numpy(arr)
        
        print(f'Got frame with {len(arr)} bytes')

        print(dr)
#         words = arr[:-5].reshape(-1, 5)
#         readoutCount = int.from_bytes( words[0:2, 0:4], byteorder='little', signed=False)
#         rowSeqCount = int.from_bytes(words[2:4, 0:4], byteorder='little', signed=False)
#         runTime = int.from_bytes(words[4:6, 0:4], byteorder='little', signed=False)
#         samples = words[6:]

#         print(f'{readoutCount=}')
#         print(f'{rowSeqCount=}')
#         print(f'{runTime=}')        
#         for s in samples:
#             value = int.from_bytes(s[0:3], byteorder='little', signed=True)
#             print(f'col {s[4]}, row {s[3]}, value 0x{value:x}')
        

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
            colBoards=1,
            rowBoards=1,
            num_row_selects=32,
            num_chip_selects=0,
#            rows=32,
            **kwargs):

        super().__init__(**kwargs)

        print(f'Starting HardwareGroup with {colBoards=}')

        rows = 256 #num_row_selects * num_chip_selects        
#        print(f'HardwareGroup with {rows} rows')

        # Open rUDP connections to the Manager board
        if simulation is False and emulate is False:
            srpUdp = pyrogue.protocols.UdpRssiPack(host=host, port=SRP_PORT, packVer=2, name='SrpRssi', groups=['NoConfig'])
            dataUdp = pyrogue.protocols.UdpRssiPack(host=host, port=DATA_PORT, packVer=2, name='DataRssi', enSsi=True, groups=['NoConfig'], jumbo=True)
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
            fifoA = rogue.interfaces.stream.Fifo(0, 0, False)
            fifoB = rogue.interfaces.stream.Fifo(0, 0, False)            
            unbatcher = rogue.protocols.batcher.SplitterV1()

            
            dataStream >> fifoA >> unbatcher >> fifoB >> packetizer.transport()

#             dataStreamDebug = rogue.interfaces.stream.Slave()
#             dataStreamDebug.setDebug(100, 'DataStreamDebug')
#             dataStream >> dataStreamDebug

#             unbatcherDebug = rogue.interfaces.stream.Slave()
#             unbatcherDebug.setDebug(100, 'UnbatcherDebug')
#             unbatcher >> unbatcherDebug

#             self.addInterface(dataStreamDebug, unbatcherDebug)            

            self.addInterface(unbatcher, packetizer, fifoA, fifoB)

            # Instantiate the board Device tree and link it to the SRP

            self.add(colBoardClass(
                name=f'ColumnBoard[{index}]',
                frontEndClass=colFeClass,
                memBase=srp,
                expand=True,
                rows=rows))
            
            pidDebug = [warm_tdm.PidDebugger(name=f'PidDebug[{i}]', hidden=False, numRows=rows, col=i, frontEnd=self.ColumnBoard[index].AnalogFrontEnd) for i in range(8)]
            saAmps = [self.ColumnBoard[index].AnalogFrontEnd.Channel[x].SAAmp for x in range(8)]
            waveGui = warm_tdm.WaveformCaptureReceiver(hidden=False, captureDev=self.ColumnBoard[index].DataPath.WaveformCapture, amplifiers=saAmps)

            # Link the data stream to the DataWriter
            if emulate is False:
                for i in range(8):
                    rateDrop = rogue.interfaces.stream.RateDrop(True, 0.1)
                    self.addInterface(rateDrop)
                    
                    fifo1 = rogue.interfaces.stream.Fifo(0, 0, False)
                    fifo2 = rogue.interfaces.stream.Fifo(0, 0, False)
                    packetizer.application(i) >> fifo1
                    fifo1 >> fifo2 >> dataWriter.getChannel(i)
                    #fifo1 >> rateDrop >> pidDebug[i]
                    self.addInterface(fifo1, fifo2, pidDebug[i])

                packetizer.application(8) >> waveGui

#                 dataDbg = rogue.interfaces.stream.Slave()
#                 dataDbg.setDebug(1000, f'DataStream_App')

                dataDbg = DataDebug()
                dataDbg.setDebug(100, 'FinalFrame')

                dataFifo = rogue.interfaces.stream.Fifo(0, 0, False)
                self.addInterface(dataFifo)
                packetizer.application(9) >> dataFifo

                dataFifo >> dataWriter.getChannel(9)
#                dataFifo >> dataDbg


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
                frontEndClass=rowFeClass,
                num_row_selects=num_row_selects,
                num_chip_selects=num_chip_selects,
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
        def Readout(arg):
            self.ReadoutList.set(list(range(arg)))

        @self.command()
        def Readout22():
            self.ReadoutList.set(list(range(22)))

        @self.command()
        def Readout32():
            self.ReadoutList.set(list(range(32)))

        @self.command()
        def Readout64():
            self.ReadoutList.set(list(range(64)))
            
        @self.command()
        def Readout80():
            self.ReadoutList.set(list(range(80)))
            

        if colBoards > 0:
            self.add(waveGui)
            for i in range(8):
                self.add(pidDebug[i])




