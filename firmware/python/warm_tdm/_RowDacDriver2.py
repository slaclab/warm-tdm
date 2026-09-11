import pyrogue as pr
import math
import numpy as np
import warm_tdm

class RowDacDriver2(pr.Device):
    def __init__(
            self,
            frontEnd,
            rows=256,
            **kwargs):
        super().__init__(**kwargs)

        self._frontEnd = frontEnd
        self.amps = [self._frontEnd.Amp[i] for i in range(32)]

        self.add(pr.RemoteVariable(
            name = 'Mode',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'TIMING',
                1: 'MANUAL'}))

        self.add(pr.RemoteVariable(
            name = 'RowBoardId',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 2,
            base = pr.UInt))

        self.add(pr.RemoteCommand(
            name = 'DacReset',
            offset = 0x08,
            bitSize = 1,
            function = pr.Command.touchOne))

        self.add(pr.RemoteVariable(
            name = 'ActivateRowIndex',
            offset = 0x10,
            bitSize = 8,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DeactivateRowIndex',
            offset = 0x14,
            bitSize = 8,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'ManualSetRaw',
            offset = 0x18,
            bitSize = 22,
            mode = 'WO',
            base = pr.UInt,
            hidden = True,
            description = ('Temporary physical-line actuation: address in bits '
                           '4:0 and raw DAC code in bits 21:8.')))

        self.add(pr.RemoteVariable(
            name = 'RowMap',
            offset = 0x1000,
            base = pr.UInt,
            numValues = rows,
            valueBits = 16,
            valueStride = 32))

        self.add(warm_tdm.FastDacMem(
            name = f'FasOn',
            offset = 0x4000,
            size = 32,
            amp = self.amps[0:32]))

        self.add(warm_tdm.FastDacMem(
            name = f'FasOff',
            offset = 0x5000,
            size = 32,
            amp = self.amps[0:32]))

    def manual_set(self, *, address, current, check_mode=True):
        """Temporarily drive one physical FAS line.

        Args:
            address: Board-local physical line index from ``RowMap`` (0..31).
            current: Requested physical output current in uA.
            check_mode: Read and verify MANUAL mode before writing. Callers
                which have already established and verified the mode may set
                this false to avoid a redundant register read per sample.

        This operation does not modify ``FasOn`` or ``FasOff`` memory. The
        returned values describe the quantized request; the interface has no
        completion readback.
        """
        address = int(address)
        if not 0 <= address < len(self.amps):
            raise ValueError(f'ManualSet address must be in 0..31, got {address}')
        if check_mode and int(self.Mode.get(read=True)) != 1:
            raise RuntimeError('ManualSet requires RowDacDriver2 Mode=MANUAL')

        code = int(self.amps[address].outCurrentToDac(float(current))) & 0x3FFF
        self.ManualSetRaw.set(value=(code << 8) | address, write=True)

        return {
            'address': address,
            'code': code,
            'current': float(self.amps[address].dacToOutCurrent(code)),
        }
