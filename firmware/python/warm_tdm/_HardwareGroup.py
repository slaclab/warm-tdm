
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

class PidDebugFilter(rogue.interfaces.stream.Master, rogue.interfaces.stream.Slave):
    """Pass through only the PID-debug frames for one column.

    The 8 per-column PID-debug streams are collapsed onto one board-local stream
    in firmware (DataPath ``U_AxiStreamMux_1`` ROUTED); the source column is
    carried in the frame body. One ``PidDebugFilter`` is instantiated per column
    and connected between the collapsed stream and that column's ``PidDebugger``:
    it accepts every frame but only re-emits (``_sendFrame``) the ones whose body
    column matches, so each downstream receiver still sees only its own column --
    the wire demux the per-column tDests used to provide moves into software.

    ``col`` lives in body byte 0, low 3 bits, i.e. header-relative offset
    ``warm_tdm.FRAME_HEADER_BYTES`` -- the same location ``PidDebugger.process``
    and the offline StreamReader read it from. The frame is forwarded unmodified;
    the downstream ``PidDebugger`` does its own 16-byte header strip.
    """

    def __init__(self, column):
        rogue.interfaces.stream.Master.__init__(self)
        rogue.interfaces.stream.Slave.__init__(self)
        self._column = column

    def _acceptFrame(self, frame):
        with frame.lock():
            if frame.getError() != 0:
                return
            size = frame.getPayload()
            if size < warm_tdm.FRAME_HEADER_BYTES + 1:
                return
            raw = bytearray(1)
            frame.read(raw, warm_tdm.FRAME_HEADER_BYTES)
            if (raw[0] & 0x7) != self._column:
                return
        # Re-emit the unmodified frame to this column's receiver.
        self._sendFrame(frame)


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
            useFloatPid=False,
            rowAddrBits=8,
            maxRows=256,
            **kwargs):

        super().__init__(**kwargs)

        # Two distinct quantities, deliberately not conflated:
        #   rowAddrBits -> the deployed RTL generic ROW_ADDR_BITS_G (3..8). The
        #     firmware row RAMs are 2**rowAddrBits deep. A property of the bitfile.
        #   maxRows     -> how many of those row slots the software maps into
        #     Rogue variables (AdcDsp per-row state, RowDacDriver.RowMap). A
        #     software choice, bounded above by the hardware depth.
        rowAddrDepth = 2 ** rowAddrBits
        if not 1 <= maxRows <= rowAddrDepth:
            raise ValueError(
                f'maxRows ({maxRows}) must be between 1 and the hardware row '
                f'depth 2**rowAddrBits = {rowAddrDepth} (rowAddrBits={rowAddrBits}).')
        rows = maxRows

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
                rows=rows,
                useFloatPid=useFloatPid))

            pidDebug = [warm_tdm.PidDebugger(name=f'PidDebug[{i}]', hidden=False, numRows=rows, col=i, frontEnd=self.ColumnBoard[index].AnalogFrontEnd) for i in range(8)]
            pidDebugFilters = [PidDebugFilter(column=i) for i in range(8)]
            saAmps = [self.ColumnBoard[index].AnalogFrontEnd.Channel[x].SAAmp for x in range(8)]
            waveGui = warm_tdm.WaveformCaptureReceiver(hidden=False, captureDev=self.ColumnBoard[index].DataPath.WaveformCapture, amplifiers=saAmps)

            # Link each stream to the DataWriter.
            #
            # File channels are namespaced by board so multiple column boards no
            # longer collide in the .dat file. The DataWriter's named accessors
            # (readoutChannel/pidDebugChannel/waveformChannel) resolve the
            # (board, stream) pair to a channel via warm_tdm.file_channel(); the
            # per-board packetizer apps here are the SEPARATE on-wire TDEST
            # namespace (app index = wire tDest[3:0], already board-demuxed
            # upstream). Board 0 maps to the single-board file layout (PID-debug
            # 1, waveform 8, readout 9).
            if emulate is False:
                # PID-debug: all 8 columns arrive collapsed on packetizer app 1
                # (wire stream 1). Tee to the file on the board's single PID-debug
                # channel, and fan out to the per-column live GUI receivers: one
                # PidDebugFilter per column subscribes to the collapsed stream and
                # passes only its own column's frames (col read from the body)
                # through to its PidDebugger.
                pidFifo = rogue.interfaces.stream.Fifo(0, 0, False)
                packetizer.application(warm_tdm.PID_DEBUG_STREAM) >> pidFifo >> dataWriter.pidDebugChannel(index)
                for i in range(8):
                    packetizer.application(warm_tdm.PID_DEBUG_STREAM) >> pidDebugFilters[i] >> pidDebug[i]
                self.addInterface(pidFifo, *pidDebugFilters, *pidDebug)

                # Waveform (packetizer app 8): drive the live GUI receiver AND
                # fold a copy into the .dat file on the board's waveform channel,
                # so one file holds every stream. The GUI path is unchanged; the
                # file path gets its own FIFO (like readout/PID) so a slow writer
                # cannot back-pressure the GUI.
                packetizer.application(8) >> waveGui
                waveFifo = rogue.interfaces.stream.Fifo(0, 0, False)
                self.addInterface(waveFifo)
                packetizer.application(8) >> waveFifo >> dataWriter.waveformChannel(index)

#                 dataDbg = rogue.interfaces.stream.Slave()
#                 dataDbg.setDebug(1000, f'DataStream_App')

                dataDbg = DataDebug()
                dataDbg.setDebug(100, 'FinalFrame')

                # Readout (packetizer app 9): the operational stream.
                dataFifo = rogue.interfaces.stream.Fifo(0, 0, False)
                self.addInterface(dataFifo)
                packetizer.application(9) >> dataFifo

                dataFifo >> dataWriter.readoutChannel(index)
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
                rows=rows,
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

        if colBoards > 0:
            self.add(waveGui)
            for i in range(8):
                self.add(pidDebug[i])




