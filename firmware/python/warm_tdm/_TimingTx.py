import pyrogue as pr


import warm_tdm

class TimingTx(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = "Mode",
            offset = 0x18,
            bitSize = 1,
            bitOffset = 0,
            enum = {
                0: "Software",
                1: "Hardware"}))

        self.add(pr.RemoteCommand(
            name = "SoftRowStrobe",
            offset = 0x1C,
            bitSize = 1,
            bitOffset = 0,
            function = pr.RemoteCommand.touchOne))
#         self.add(pr.RemoteVariable(
#             name = 'EnOutput',
#             mode = 'RW',
#             offset = 0x30,
#             bitOffset = 0,
#             bitSize = 1,
#             base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = "TxRefClkFreqRaw",
            mode = 'RO',
            offset = 0x60,
            bitOffset = 0,
            bitSize = 32,
            hidden = True))

        self.add(pr.LinkVariable(
            name = "TxRefClkFreq",
            mode = "RO",
            disp = '{:0.3f}',
            units = 'MHz',
            dependencies = [self.TxRefClkFreqRaw],
            linkedGet = lambda: self.TxRefClkFreqRaw.value()*1.0E-6))

        self.add(pr.RemoteVariable(
            name = "TxWordClkFreqRaw",
            mode = 'RO',
            offset = 0x64,
            bitOffset = 0,
            bitSize = 32,
            hidden = True))

        self.add(pr.LinkVariable(
            name = "TxWordClkFreq",
            mode = "RO",
            disp = '{:0.3f}',
            units = 'MHz',
            dependencies = [self.TxWordClkFreqRaw],
            linkedGet = lambda: self.TxWordClkFreqRaw.value()*1.0E-6))


        self.add(pr.RemoteCommand(
            name = 'StartRun',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            function = pr.Command.toggle))

        self.add(pr.RemoteCommand(
            name = 'EndRun',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 1,
            function = pr.Command.toggle))

        self.add(pr.RemoteCommand(
            name = 'WaveformCapture',
            offset = 0x20,
            bitOffset = 0,
            bitSize = 1,
            function = pr.Command.touchOne))

        self.add(pr.RemoteVariable(
            name = 'WaveformCaptureTime',
            offset = 0x28,
            bitOffset = 0,
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RowPeriodCycles',
            mode = 'RW',
            offset = 0x08,
            bitOffset = 0,
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.LinkVariable(
            name = 'RowRate',
            mode = 'RW',
            dependencies = [self.RowPeriodCycles],
            disp = '{:0.03f}',
            units = 'kHz (kRows/sec)',
            linkedGet = lambda read: 1.0e-3 / (self.RowPeriod.get(read=read) * 8.0e-9),
            linkedSet = lambda value, write: self.RowPeriod.set(1.0 / ((value * 1.0e3) * 8.0e-9), write=write)))

        self.add(pr.LinkVariable(
            name = 'RowPeriod',
            mode = 'RW',
            dependencies = [self.RowRate],
            disp = '{:0.03f}',
            units = '\u03bcSec',
            linkedGet = lambda read: 1.0e3 / self.RowRate.get(read=read),
            linkedSet = lambda value, write: self.RowRate.set(1.0e-3 / value)))

        self.add(pr.RemoteVariable(
            name = 'NumRows',
            mode = 'RW',
            offset = 0x0C,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'SampleStartTime',
            mode = 'RW',
            offset = 0x10,
            bitOffset = 0,
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'SampleEndTime',
            mode = 'RW',
            offset = 0x14,
            bitOffset = 0,
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'LoadDacsTime',
            mode = 'RW',
            offset = 0x24,
            bitOffset = 0,
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'Running',
            mode = 'RO',
            offset = 0x30,
            bitOffset = 0,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'Sampling',
            mode = 'RO',
            offset = 0x30,
            bitOffset = 1,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'RowNum',
            mode = 'RO',
            offset = 0x34,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RowTime',
            mode = 'RO',
            offset = 0x38,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RunTime',
            mode = 'RO',
            offset = 0x40,
            bitOffset = 0,
            bitSize = 64,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'ReadoutCount',
            mode = 'RO',
            offset = 0x48,
            bitOffset = 0,
            bitSize = 64,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'XbarTxClkSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))


        self.add(pr.RemoteVariable(
            name = 'XbarRxClkSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 1,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))

        self.add(pr.RemoteVariable(
            name = 'XbarTxDataSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 4,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))


        self.add(pr.RemoteVariable(
            name = 'XbarRxDataSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 5,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))

        self.add(pr.RemoteVariable(
            name = 'XbarTxMgtSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 8,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))


        self.add(pr.RemoteVariable(
            name = 'XbarRxMgtSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 9,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))

        self.add(pr.RemoteVariable(
            name = 'XbarTxTimingSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 12,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))


        self.add(pr.RemoteVariable(
            name = 'XbarRxTimingSrc',
            mode = 'RW',
            offset = 0x50,
            bitOffset = 13,
            bitSize = 1,
            enum = {
                0: 'RJ-45 RX',
                1: 'FPGA TX'}))


        self.add(pr.RemoteVariable(
            name = 'RowIndexOrder',
            offset = 0x1000,
            valueBits = 8,
            numValues = 256,
            valueStride = 32,
            base = pr.UInt,
            mode = 'RW'))
