import pyrogue as pr

import surf
import surf.devices.analog_devices

import numpy as np

import warm_tdm

DEFAULT_LOADING = {
    'SA_BIAS_SHUNT_R':15.0e3,
    'SA_OFFSET_R':4.02e3,
    'SA_AMP_FB_R':1.1e3,
    'SA_AMP_GAIN_R':100,
    'SA_AMP_GAIN_2':11,
    'SA_AMP_GAIN_3':1.5,
    'SA_FB_FSADJ_R':2.0e3,
    'SA_FB_DAC_LOAD_R':25.0,
    'SA_FB_AMP_GAIN':-4.7,
    'SA_FB_SHUNT_R':7.15e3,
    'SQ1_FB_FSADJ_R':2.0e3,
    'SQ1_FB_DAC_LOAD_R':25.0,
    'SQ1_FB_AMP_GAIN':-4.7,
    'SQ1_FB_SHUNT_R':11.3e3,
    'SQ1_BIAS_FSADJ_R':2.0e3,
    'SQ1_BIAS_DAC_LOAD_R':25.0,
    'SQ1_BIAS_AMP_GAIN':-4.7,
    'SQ1_BIAS_SHUNT_R':10.0e3}


class ColumnLoading(pr.Device):

    def __init__(self, column, **kwargs):
        super().__init__(**kwargs)

        self.column = column

        self.add(pr.LocalVariable(
            name = 'SA_BIAS_SHUNT_R',
            value = 15.0e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_OFFSET_R',
            value = 4.02e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_AMP_FB_R',
            value = 1.1e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_AMP_GAIN_R',
            value = 100,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_AMP_GAIN_2',
            value = 11,))
        
        self.add(pr.LocalVariable(
            name = 'SA_AMP_GAIN_3',
            value = 1.5,))
        
        self.add(pr.LocalVariable(
            name = 'SA_FB_FSADJ_R',
            value = 2.0e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_FB_DAC_LOAD_R',
            value = 25.0,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SA_FB_AMP_GAIN',
            value = -4.7,))
        
        self.add(pr.LocalVariable(
            name = 'SA_FB_SHUNT_R',
            value = 7.15e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_FB_FSADJ_R',
            value = 2.0e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_FB_DAC_LOAD_R',
            value = 25.0,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_FB_AMP_GAIN',
            value = -4.7,))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_FB_SHUNT_R',
            value = 11.3e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_BIAS_FSADJ_R',
            value = 2.0e3,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_BIAS_DAC_LOAD_R',
            value = 25.0,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_BIAS_AMP_GAIN',
            value = -4.7,))
        
        self.add(pr.LocalVariable(
            name = 'SQ1_BIAS_SHUNT_R',
            value = 10.0e3,
            units = u'\u03a9'))
        
        sa_vars = [
            self.SA_OFFSET_R,
            self.SA_AMP_FB_R,
            self.SA_AMP_GAIN_R,
            self.SA_AMP_GAIN_2,
            self.SA_AMP_GAIN_3]


        self.add(pr.LinkVariable(
            name = 'AmpInConvFactor',
            units = u'\u03bcV/ADC',
            disp = '{:0.3f}',
            mode = 'RO',
            dependencies = sa_vars,
            linkedGet = lambda read: 1.0e6 * self.ampVin(1/2**13, 0.0)))

        self.add(pr.LinkVariable(
            name = 'AmpSaGain',
            disp = '{:0.3f}',
            mode = 'RO',
            dependencies = sa_vars,
            linkedGet = lambda read: 1 / self.ampVin(1.0, 0.0)))

        
    def ampVin(self, vout, voffset):
        """Calculate SA_OUT an amplifier input given amp output and voffset"""

        G_OFF = 1.0/self.SA_OFFSET_R.value()
        G_FB = 1.0/self.SA_AMP_FB_R.value()
        G_GAIN = 1.0/self.SA_AMP_GAIN_R.value()

        V_OUT_1 = vout/(self.SA_AMP_GAIN_2.value()*self.SA_AMP_GAIN_3.value())

        SA_OUT = ((G_OFF * voffset) + (G_FB * V_OUT_1)) / (G_OFF + G_FB + G_GAIN)

        return SA_OUT



class ColumnBoardLoading(pr.Device):

    def __init__(self, overrides={}, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            col_overrides = {}
            if i in overrides:
                col_overrides = overrides[i]

            self.add(ColumnLoading(
                name = f'Column[{i}]',
                column = i,
                defaults = col_overrides))

        self.ampVinVec = np.vectorize(self.ampVin)

    def ampVin(self, vout, voffset, col):
        return self.Column[col].ampVin(vout, voffset)

    def deps(self, typ, val):
        return [v for col in range(8) for k,v in self.Column[col].variables.items() if k.startswith(typ) and k.endswith(val)]



class ColumnModule(pr.Device):
    def __init__(self,
                 amplifierClass=warm_tdm.ColumnBoardC00SaAmp,
#                 loading={},
                 rows=1,
                 **kwargs):
        super().__init__(**kwargs)

        # SA Signal Amplifier Models
        for i in range(8):
            self.add(amplifierClass(
                name = f'Amp[{i}]'))

        self.amplifiers = [self.Amp[i] for i in range(8)]
 
        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))

        self.add(warm_tdm.DataPath(
            offset = 0xC0300000,
            expand = True,))

        self.add(warm_tdm.Ad5679R(
            name = 'SaBiasDac',
            hidden = True,
            offset = 0xC0700000))

        self.add(warm_tdm.SaBiasOffset(
            dac = self.SaBiasDac,
#            loading = self.Loading,
            waveformTrigger = self.DataPath.WaveformCapture.WaveformTrigger))

        self.add(warm_tdm.Ad5679R(
            name = 'TesBiasDac',
            hidden = True,
            offset = 0xC0701000))

        self.add(warm_tdm.TesBias(
            dac = self.TesBiasDac))

        self.add(warm_tdm.FastDacDriver(
            name = 'SAFb',
            offset = 0xC0600000,
            rows = rows,            
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Bias',
            offset = 0xC0400000,
            rows = rows,
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Fb',
            offset =0xC0500000,
            rows = rows,
        ))


        self.add(surf.devices.analog_devices.Ad9681Config(
            enabled = True,
            offset = 0xC0200000))

        #########################################
        # Compute SA Out based on loading options
        #########################################
        self.add(pr.LinkVariable(
            name = 'SaOutAdc',
            description = 'SA Signal voltage as measured at ADC, after amplification',
            variable = self.DataPath.WaveformCapture.AdcAverage,
            units = 'V',
            mode = 'RO',
            disp = '{:0.03f}'))

        cols = list(range(8))

        def _saOutGet(*, read=True, index=-1, check=True):
            #print(f'ColumnModule._saOutGet({read=}, {index=}, {check=})')
            with self.root.updateGroup():
                adc = self.SaOutAdc.get(read=read, index=index, check=check)
                offset = self.SaBiasOffset.OffsetVoltageArray.get(read=read, index=index, check=check)
                if index == -1:
                    ret = np.array([self.Amp[i].ampVin(adc, offset) * 1e3 for i in range(8)])
                    return ret
                else:
                    ret = self.Amp[index].ampVin(adc, offset) * 1e3
                    return ret

        def _saOutNormGet(*, read=True, index=-1, check=True):
            #print(f'ColumnModule._saOutNormGet({read=}, {index=}, {check=})')
            with self.root.updateGroup():
                adc = self.SaOutAdc.get(read=read, index=index, check=check)
                offset = 0.0
                if index == -1:
                    ret = np.array([self.Amp[i].ampVin(adc, offset) * 1e3 for i in range(8)])
                    return ret
                else:
                    ret = self.Amp[index].ampVin(adc, offset) * 1e3
                    return ret


        self.add(pr.LinkVariable(
            name = 'SaOut',
            description = 'Calculated SA Signal value given ADC voltage, Amplifier model and Offset value',
            dependencies = [self.SaOutAdc, *[x for x in self.SaBiasOffset.OffsetVoltage.values()]],
            units = 'mV',
            disp = '{:0.03f}',
            linkedGet = _saOutGet))

        self.add(pr.LinkVariable(
            name = 'SaOutNorm',
            description = 'Calculated SA Signal value given ADC voltage with offset=0',
            dependencies = [self.SaOutAdc],
            units = 'mV',
            disp = '{:0.03f}',
            linkedGet = _saOutNormGet))



#         self.add(pr.RemoteVariable(
#             name = f'TestRam',
#             offset = 0xC0800000,
#             base = pr.UInt,
#             mode = 'RW',
#             bitSize = 8*2**14,
#             numValues = 1024*4,
#             valueBits = 32,
#             valueStride = 32))

#         @self.command()
#         def SetTestRam(arg):
#             print(arg)
#             offset, size = arg
# #            ram = np.linspace(0, 2**32-1, 2**13-25, endpoint=False, dtype=np.uint32)
#             ram = np.linspace(0, 2**32-1, size, endpoint=False, dtype=np.uint32)
#             self.TestRam.set(value=ram, index=offset, write=True)


        @self.command()
        def AllFastDacs(arg):
            for v in self.SAFb.Override.values():
                v.set(value=arg, write=True)

            for v in self.SQ1Fb.Override.values():
                v.set(value=arg, write=True)

            for v in self.SQ1Bias.Override.values():
                v.set(value=arg, write=True)


        @self.command()
        def InitDacAdc():
            self.Ad9681Config.enable.set(True)
            self.Ad9681Config.ReadDevice()
            self.Ad9681Config.InternalPdwnMode.setDisp('Full Power Down')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')
            self.Ad9681Config.InternalPdwnMode.setDisp('Digital Reset')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')

            self.DataPath.Ad9681Readout.Relock()
            self.DataPath.Ad9681Readout.LostLockCountReset()

            self.SaBiasDac.ZeroVoltages()
            self.TesBiasDac.ZeroVoltages()

    def initialize(self):
        self.InitDacAdc()
