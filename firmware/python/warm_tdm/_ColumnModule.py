import pyrogue as pr

import surf
import surf.devices.analog_devices

import numpy as np

import warm_tdm


class ArrayDevice(pr.Device):
    """ """
    def __init__(self, *, arrayClass, number, stride=0, arrayArgs=None, **kwargs):
        if 'name' not in kwargs:
            kwargs['name'] = f'{arrayClass.__name__}Array'
        super().__init__(**kwargs)

        if arrayArgs is None:
            arrayArgs = [{} for x in range(number)]
        elif isinstance(arrayArgs, dict):
            arrayArgs = [arrayArgs.copy() for x in range(number)]

        for i in range(number):
            args = arrayArgs[i]
            if 'name' in args:
                name = args.pop('name')
                name = f'{name}[{i}]'
            else:
                name = f'{arrayClass.__name__}[{i}]'
            self.add(arrayClass(
                name=name,
                offset=i*stride,
                **args))


class ColumnModule(pr.Device):
    def __init__(self,
                 frontEndClass,
#                 loading={},
                 rows=256,
                 **kwargs):
        super().__init__(**kwargs)

        # SA Signal Amplifier Models        
#         self.add(pr.ArrayDevice(
#             name = 'AmpLoading',
#             arrayClass = amplifierClass,
#             number = 8,
#             arrayArgs = [{'name': f'Amp[{i}]'} for i in range(8)]))
        
#         self.amplifiers = [self.AmpLoading.Amp[i] for i in range(8)]
        self.add(frontEndClass(
            name='AnalogFrontEnd'))
 
        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True,
            therm_channels = [0, 1, 8, 9]))

        self.add(warm_tdm.DataPath(
            offset = 0xC0300000,
            expand = True,
            rows = rows,
            frontEnd=self.AnalogFrontEnd))

        self.add(warm_tdm.Ad5679R(
            name = 'SaBiasDac',
            groups = ['NoConfig'],
            hidden = True,
            offset = 0xC0700000))

        self.add(warm_tdm.SaBiasOffset(
            dac = self.SaBiasDac,
            frontEnd = self.AnalogFrontEnd,
            waveformTrigger = self.DataPath.WaveformCapture.WaveformTrigger))

        self.add(warm_tdm.Ad5679R(
            name = 'TesBiasDac',
            hidden = False,
            offset = 0xC0701000))

        self.add(warm_tdm.TesBias(
            offset = 0xC0702000,
            dac = self.TesBiasDac,
            frontEnd = self.AnalogFrontEnd))

        self.add(warm_tdm.FastDacDriver(
            name = 'SAFb',
            offset = 0xC0600000,
            frontEnd = self.AnalogFrontEnd,            
#            shunt = 7.15e3,
            rows = rows,            
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Bias',
            offset = 0xC0400000,
            frontEnd = self.AnalogFrontEnd,            
#            shunt = 10.0e3,
            rows = rows,
        ))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Fb',
            offset =0xC0500000,
            frontEnd = self.AnalogFrontEnd,            
 #           shunt = 11.3e3,
            rows = rows,
        ))


        self.add(surf.devices.analog_devices.Ad9681Config(
            enabled = False,
            offset = 0xC0200000))

        #########################################
        # Compute SA Out based on amplifier config
        #########################################
        self.add(pr.LinkVariable(
            name = 'SaOutAdc',
            description = 'SA Signal voltage as measured at ADC, after amplification',
            variable = self.DataPath.WaveformCapture.AdcAverage,
            units = 'V',
            mode = 'RO',
            disp = '{:0.03f}'))

        cols = list(range(8))

        saOutAmps = [self.AnalogFrontEnd.Channel[x].SAAmp for x in range(8)]

        def _saOutGet(*, read=True, index=-1, check=True):
            #print(f'ColumnModule._saOutGet({read=}, {index=}, {check=})')
            with self.root.updateGroup():
                adcs = self.SaOutAdc.get(read=read, index=index, check=check)
                offsets = self.SaBiasOffset.OffsetVoltageArray.get(read=read, index=index, check=check)
                if index == -1:
                    ret = np.array([saOutAmps[i].ampVin(adcs[i], offsets[i]) * 1e3 for i in range(8)])
                    return ret
                else:
                    ret = saOutAmps[index].ampVin(adcs, offsets) * 1e3
                    return ret

        def _saOutNormGet(*, read=True, index=-1, check=True):
            #print(f'ColumnModule._saOutNormGet({read=}, {index=}, {check=})')
            with self.root.updateGroup():
                adcs = self.SaOutAdc.get(read=read, index=index, check=check)
                offset = 0.0
                if index == -1:
                    ret = np.array([saOutAmps[i].ampVin(adcs[i], offset) * 1e3 for i in range(8)])
                    return ret
                else:
                    ret = saOutAmps[index].ampVin(adcs, offset) * 1e3
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
            enable = self.Ad9681Config.enable.get()
            self.Ad9681Config.enable.set(True)
            self.Ad9681Config.ReadDevice()
            self.Ad9681Config.InternalPdwnMode.setDisp('Full Power Down')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')
            self.Ad9681Config.InternalPdwnMode.setDisp('Digital Reset')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')
            self.Ad9681Config.enable.set(enable)

            self.DataPath.Ad9681Readout.Relock()
            self.DataPath.Ad9681Readout.LostLockCountReset()

            self.SaBiasDac.ZeroVoltages()
            self.TesBiasDac.ZeroVoltages()

    def initialize(self):
        self.InitDacAdc()
