import pyrogue as pr

import surf.dsp.fixed

import warm_tdm



class AdcDsp(pr.Device):
    def __init__(self, numRows=64, **kwargs):
        super().__init__(**kwargs)

        ACCUM_BITS = 16
        COEF_BITS = 12
        SUM_BITS = 18
        RESULT_BITS = 32

        COEF_BASE = pr.Fixed(12, 8)

        self.add(pr.RemoteVariable(
            name = 'AdcOffsets',
            offset = 0x000,
            base = pr.Int,
            mode = 'RW',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 16,
            valueStride = 32))

        
#         self.add(pr.ArrayDevice(
#             name = 'AdcOffsets',
#             offset = 0,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs= [{
#                 'name': f'Row[{i}]',
#                 'base': pr.Int,
# #                'disp' : '{:#x}',
#                 'mode': 'RW',
#                 'bitSize':16} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x1000,
            base = pr.Int,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = ACCUM_BITS,
            valueStride = 32))


#         self.add(pr.ArrayDevice(
#             name = 'AccumError',
#             offset = 0x100,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': pr.Int,
#                 'mode': 'RO',
#                 'bitSize':ACCUM_BITS} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x2000,
            base = pr.Int,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = SUM_BITS,
            valueStride = 32))
        

#         self.add(pr.ArrayDevice(
#             name = 'SumAccum',
#             offset = 0x200,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': pr.Int,
#                 'mode': 'RO',
#                 'bitSize':SUM_BITS} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'P_COEF',
            offset = 0x3000,
            base = COEF_BASE,
            mode = 'RW',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = COEF_BITS,
            valueStride = 32))


#         self.add(pr.ArrayDevice(
#             name = 'P_COEF',
#             offset = 0x300,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': COEF_BASE,
#                 'mode': 'RW',
#                 'bitSize':COEF_BITS} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'I_COEF',
            offset = 0x4000,
            base = COEF_BASE,
            mode = 'RW',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = COEF_BITS,
            valueStride = 32))

#         self.add(pr.ArrayDevice(
#             name = 'I_COEF',
#             offset = 0x400,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': COEF_BASE,
#                 'mode': 'RW',
#                 'bitSize':COEF_BITS} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'D_COEF',
            offset = 0x5000,
            base = COEF_BASE,
            mode = 'RW',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = COEF_BITS,
            valueStride = 32))


#         self.add(pr.ArrayDevice(
#             name = 'D_COEF',
#             offset = 0x500,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': COEF_BASE,
#                 'mode': 'RW',
#                 'bitSize':COEF_BITS} for i in range(numRows)]))

        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x6000,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = RESULT_BITS,
            valueStride = 32))
        
#         self.add(pr.ArrayDevice(
#             name = 'PidResults',
#             offset = 0x600,
#             number=numRows,
#             stride=4,
#             arrayClass=pr.RemoteVariable,
#             arrayArgs=[{
#                 'name': f'Row[{i}]',
#                 'base': pr.Fixed(32,8),
#                 'mode': 'RO',
#                 'bitSize':RESULT_BITS} for i in range(numRows)]))
        
        
        self.add(pr.RemoteVariable(
            name = 'FilterResults',
            offset = 0x7000,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 16,
            valueStride = 32))

#         self.add(surf.dsp.fixed.FirFilterMultiChannel(
#             offset = 0x8000,
#             numberTaps = 10,
#             numberChannels = 64,
#             dataWordBitSize = 16))
