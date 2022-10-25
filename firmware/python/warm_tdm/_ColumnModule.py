import pyrogue as pr

import surf
import surf.devices.analog_devices

import numpy as np

import warm_tdm


DEFAULT_LOADING = {ch: {
    'SA_BIAS_SHUNT_R':15.0e3,
    'SA_OFFSET_R':4.02e3,
    'SA_AMP_FB_R':1.1e3,
    'SA_AMP_GAIN_R':100,
    'SA_AMP_GAIN_2':11,
    'SA_AMP_GAIN_3':1.5,
    'SA_FB_FSADJ_R':2.0e3,
    'SA_FB_DAC_LOAD_R':25.0,
    'SA_FB_AMP_GAIN_R':-4.7,
    'SA_FB_SHUNT_R':7.15e3,
    'SQ1_FB_FSADJ_R':2.0e3,                     
    'SQ1_FB_DAC_LOAD_R':25.0,
    'SQ1_FB_AMP_GAIN_R':-4.7,
    'SQ1_FB_SHUNT_R':7.15e3,
    'SQ1_BIAS_FSADJ_R':2.0e3,                     
    'SQ1_BIAS_DAC_LOAD_R':25.0,
    'SQ1_BIAS_AMP_GAIN_R':-4.7,
    'SQ1_BIAS_SHUNT_R':7.15e3} for ch in range(8)}


class ColumnModule(pr.Device):
    def __init__(self,
                 # Channels 0 and 1 have FB attached after first stage
                 waveform_stream,                 
                 loading={
                     0: {
                         'SA_AMP_FB_R': 1.0,
                         'SA_OFFSET_R': 1.0e20,
                         'SA_AMP_GAIN_R': 1.0e20},
                     1: {
                         'SA_AMP_FB_R': 1.0,
                         'SA_OFFSET_R': 1.0e20,
                         'SA_AMP_GAIN_R': 1.0e20}},                     
                 rows=64,
                 **kwargs):
        super().__init__(**kwargs)

        # Write any entries in loading over top of the default loading values
        self.loading = DEFAULT_LOADING.copy()
        print(self.loading)
        
        for ch, d in loading.items():
            for k, v in d.items():
                print(f'{ch=}, {d=}, {k=}, {v=}')
                self.loading[ch][k] = v


        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))

        self.add(warm_tdm.DataPath(
            offset = 0xC0300000,
            expand = True,
            waveform_stream = waveform_stream))

        self.add(warm_tdm.Ad5679R(
            name = 'SaBiasDac',
            hidden = True,
            offset = 0xC0700000))

        self.add(warm_tdm.SaBiasOffset(
            dac = self.SaBiasDac,
            loading = self.loading,
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
            rfsadj = {col: d['SA_FB_FSADJ_R'] for col, d in self.loading.items()},
            dacLoad = {col: d['SA_FB_DAC_LOAD_R'] for col, d in self.loading.items()},
            ampGain = {col: d['SA_FB_AMP_GAIN_R'] for col, d in self.loading.items()},
            outResistance = {col: d['SA_FB_SHUNT_R'] for col, d in self.loading.items()},
            waveformTrigger = self.DataPath.WaveformCapture.WaveformTrigger
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Bias',
            offset = 0xC0400000,
            rows = rows,
            rfsadj = {col: d['SQ1_BIAS_FSADJ_R'] for col, d in self.loading.items()},
            dacLoad = {col: d['SQ1_BIAS_DAC_LOAD_R'] for col, d in self.loading.items()},
            ampGain = {col: d['SQ1_BIAS_AMP_GAIN_R'] for col, d in self.loading.items()},
            outResistance = {col: d['SQ1_BIAS_SHUNT_R'] for col, d in self.loading.items()},
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Fb',
            offset =0xC0500000,
            rows = rows,
            rfsadj = {col: d['SQ1_FB_FSADJ_R'] for col, d in self.loading.items()},
            dacLoad = {col: d['SQ1_FB_DAC_LOAD_R'] for col, d in self.loading.items()},
            ampGain = {col: d['SQ1_FB_AMP_GAIN_R'] for col, d in self.loading.items()},
            outResistance = {col: d['SQ1_FB_SHUNT_R'] for col, d in self.loading.items()},
        ))


        self.add(surf.devices.analog_devices.Ad9681Config(
            enabled = True,
            offset = 0xC0200000))

        #########################################
        # Compute SA Out based on loading options
        #########################################
        self.add(pr.LinkVariable(
            name = 'SaOutAdc',
            variable = self.DataPath.WaveformCapture.AdcAverage,
            units = 'V',
            mode = 'RO',
            disp = '{:0.03f}'))


        def ampVin(Vout, Voffset, col):
            lo = self.loading[col]
            G_OFF = 1.0/lo['SA_OFFSET_R']
            G_FB = 1.0/lo['SA_AMP_FB_R']
            G_GAIN = 1.0/lo['SA_AMP_GAIN_R']

            V_OUT_1 = Vout/(lo['SA_AMP_GAIN_2']*lo['SA_AMP_GAIN_3'])
            
            SA_OUT = ((G_OFF * Voffset) + (G_FB * V_OUT_1)) / (G_OFF + G_FB + G_GAIN)
            return SA_OUT

        ampVinVec = np.vectorize(ampVin)
        cols = list(range(8))

        def _saOutGet(*, read=True, index=-1, check=True):
            with self.root.updateGroup():
                adc = self.SaOutAdc.get(read=read, index=index, check=check)
                offset = self.SaBiasOffset.OffsetVoltageArray.get(read=read, index=index, check=check)
                if index == -1:
                    ret = ampVinVec(adc, offset, cols) * 1e3
                    return ret
                else:
                    ret = ampVin(adc, offset, index) * 1e3
                    return ret

        def _saOutNormGet(*, read=True, index=-1, check=True):
            with self.root.updateGroup():
                adc = self.SaOutAdc.get(read=read, index=index, check=check)
                offset = 0.0
                if index == -1:
                    ret = ampVinVec(adc, offset, cols) * 1e3
                    return ret
                else:
                    ret = ampVin(adc, offset, index) * 1e3
                    return ret
                    
        
        self.add(pr.LinkVariable(
            name = 'SaOut',
            dependencies = [self.SaOutAdc, *[x for x in self.SaBiasOffset.OffsetVoltage.values()]],
            units = 'mV',
            disp = '{:0.03f}',            
            linkedGet = _saOutGet))

        self.add(pr.LinkVariable(
            name = 'SaOutNorm',
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
            
