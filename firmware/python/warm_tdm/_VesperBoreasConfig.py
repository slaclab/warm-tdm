import pyrogue as pr
import numpy as np

class VesperBoreasConfig(pr.Device):
    def __init__(self, saBiasDac, saOffsetDac, tesBiasDac, saFbDac, sq1BiasDac, sq1FbDac, auxDac, **kwargs):

        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'FastDacOff',
            value = 0x0))

        self.add(pr.LocalVariable(
            name = 'FastDacOn',
            value = 0x1444))

        on = self.FastDacOn
        off = self.FastDacOff

        class FastDacLinkVariable(pr.LinkVariable):
            def __init__(self, dac, **kwargs):
                super().__init__(
                    dependencies=[dac, off, on],
                    linkedSet=self._set,
                    linkedGet=self._get,
                    enum = {0: 'Off',
                            1: 'On',
                            2: 'Unknown'},
                    **kwargs)
                self._dac = dac

            def _set(self, value, write):
                if value == 0:
                    self._dac.set(off.value())
                else:
                    self._dac.set(on.value())

            def _get(self, read):
                v = self._dac.get(read=read)
                if v == off.value():
                    return 0
                if v == on.value():
                    return 1
                print(f'Warning! DAC value for {self.path} ({v}) does not corespond to FastDacOn ({on.value()}) or FastDacOff ({fff.value()})')
                return 2

        # SA FB DAC Variables
        self.add(FastDacLinkVariable(
            name = 'INA_gain_0',
            dac = saFbDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'I_cntrlb2',
            dac = saFbDac.OverrideRaw[7]))

        # SQ1 Bias DAC Variables
        self.add(FastDacLinkVariable(
            name = 'I_cnrl_c1',
            dac = sq1BiasDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'INA_gain_2',
            dac = sq1BiasDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'Iref_sel_0',
            dac = sq1BiasDac.OverrideRaw[7]))

        # SQ1 FB DAC Variables
        self.add(FastDacLinkVariable(
            name = 'EN_INA',
            dac = sq1FbDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'I_cnrl_b0',
            dac = sq1FbDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'Chicken',
            dac = sq1FbDac.OverrideRaw[7]))

        # AUX DAC Variables
        self.add(FastDacLinkVariable(
            name = 'I_cntlc_1',
            dac = auxDac.OverrideRaw[0]))

        self.add(FastDacLinkVariable(
            name = 'EN_BLK_INA',
            dac = auxDac.OverrideRaw[1]))

        self.add(FastDacLinkVariable(
            name = 'INA_gain_1',
            dac = auxDac.OverrideRaw[2]))

        self.add(FastDacLinkVariable(
            name = 'INA_sel',
            dac = auxDac.OverrideRaw[3]))

        self.add(FastDacLinkVariable(
            name = 'I_cntlb_1',
            dac = auxDac.OverrideRaw[4]))

        self.add(FastDacLinkVariable(
            name = 'gallo_INA',
            dac = auxDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'Iref_sel_1',
            dac = auxDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'I_cntlc_2',
            dac = auxDac.OverrideRaw[7]))

        class TesLinkVariable(pr.LinkVariable):
            def __init__(self, dac, **kwargs):
                super().__init__(
                    dependencies=[dac],
                    linkedSet=self._set,
                    linkedGet=self._get,
                    disp = '{:0.3f}',
                    units = '\u03bcA',
                    **kwargs)
                self._dac = dac

            # Conversion formulas for DAC units to reference currents
            def _set(self, value, write):
                dac = np.clip(value, 0.0, 250.0)
                dac = dac / 250.0
                dac = dac * 0xFFFF
                dac = int(dac)
                self._dac.set(dac, write=write)

            def _get(self, read):
                dac = self._dac.get(read=read)
                dac = dac / 0xFFFF
                dac = dac * 250.0
                return dac

        self.add(TesLinkVariable(
            name = 'Boreas_A_Iref_io_INA1',
            dac = tesBiasDac.Dac[4])) # 2P

        self.add(TesLinkVariable(
            name = 'Boreas_A_Iref_SLVT_INA1',
            dac = tesBiasDac.Dac[5])) # 2N

        self.add(TesLinkVariable(
            name = 'Vesper_D_Iref_io_INA1',
            dac = tesBiasDac.Dac[6])) # 3P

        self.add(TesLinkVariable(
            name = 'Vesper_D_Iref_SLVT_INA1',
            dac = tesBiasDac.Dac[7])) # 3N

        self.add(TesLinkVariable(
            name = 'Boreas_A_Iref_io_INA2',
            dac = tesBiasDac.Dac[8])) # 4P

        self.add(TesLinkVariable(
            name = 'Boreas_A_Iref_SLVT_INA2',
            dac = tesBiasDac.Dac[9])) # 4N

        self.add(TesLinkVariable(
            name = 'Boreas_B_Iref_io_INA1',
            dac = tesBiasDac.Dac[10])) # 5P

        self.add(TesLinkVariable(
            name = 'Boreas_B_Iref_SLVT_INA1',
            dac = tesBiasDac.Dac[11])) # 5P

        self.add(TesLinkVariable(
            name = 'Vesper_C_IRef_io_INA1',
            dac = tesBiasDac.Dac[12])) # 6P

        self.add(TesLinkVariable(
            name = 'Vesper_C_IRef_SLVT_INA1',
            dac = tesBiasDac.Dac[13])) # 6N

        self.add(TesLinkVariable(
            name = 'Boreas_B_Iref_io_INA2',
            dac = tesBiasDac.Dac[14])) # 7P

        self.add(TesLinkVariable(
            name = 'Boreas_B_Iref_SLVT_INA2',
            dac = tesBiasDac.Dac[15])) # 7N

        class SaBiasLinkVariable(pr.LinkVariable):
            def __init__(self, dac, **kwargs):
                super().__init__(
                    dependencies=[dac],
                    linkedSet=self._set,
                    linkedGet=self._get,
                    units = 'V',
                    disp = '{:0.3f}',
                    **kwargs)
                self._dac = dac

            # Conversion formulas for DAC units to reference voltages
            def _set(self, value, write):
                dac = np.clip(value, 0.0, 0.9)
                dac = dac / 0.9
                dac = dac * 0xFFFF
                dac = int(dac)
                self._dac.set(dac, write=write)

            def _get(self, read):
                dac = self._dac.get(read=read)
                dac = dac / 0xFFFF
                dac = dac * 0.9
                return dac

        self.add(SaBiasLinkVariable(
            name = 'Boreas_AB_VbulkA_INA1',
            dac = saBiasDac.Dac[12])) # 6P

        self.add(SaBiasLinkVariable(
            name = 'Boreas_AB_VbulkB_INA1',
            dac = saBiasDac.Dac[13])) # 6N

        self.add(SaBiasLinkVariable(
            name = 'Vesper_CD_VbulkA_INA1',
            dac = saBiasDac.Dac[14])) # 7P

        self.add(SaBiasLinkVariable(
            name = 'Vesper_CD_VbulkB_INA1',
            dac = saBiasDac.Dac[15])) # 7N

        class SaOffsetLinkVariable(pr.LinkVariable):
            def __init__(self, dac, **kwargs):
                super().__init__(
                    dependencies=[dac],
                    linkedSet=self._set,
                    linkedGet=self._get,
                    units = 'V',
                    disp = '{:0.3f}',
                    **kwargs)
                self._dac = dac

            # Conversion formulas for DAC units to reference voltages
            def _set(self, value, write):
                # Constrain the value to allowable range
                if value < 0.7:
                    value = 0.7
                if value > 0.95:
                    value = 0.95

                # Subtract the .7V offset
                value = value - 0.7

                self._dac.set(value, write=write)

            def _get(self, read):
                value = self._dac.get(read=read)
                # Apply .7V offset
                return value + 0.7

        self.add(SaOffsetLinkVariable(
            name = 'VDDA',
            dac = saOffsetDac.DacVoltage[7]))


        gain_enum = {
            0: '20',
            1: '50',
            2: '100',
            3: '150',
            4: '200',
            5: '300',
            6: '600'}

        gain_enum_rev = {v:k for k,v in gain_enum.items()}


        def _getGain(read):
            with self.root.updateGroup():
                gain = self.INA_gain_2.get(read=read)
                gain <<= 1
                gain |= self.INA_gain_1.get(read=read)
                gain <<= 1
                gain |= self.INA_gain_0.get(read=read)
                return gain #gain_enum[gain]

        def _setGain(value, write):
            with self.root.updateGroup():
                self.INA_gain_0.set(value&1, write=write)
                self.INA_gain_1.set((value>>1)&1, write=write)
                self.INA_gain_2.set((value>>2)&1, write=write)

        self.add(pr.LinkVariable(
            name = 'GAIN_RAW',
            dependencies = [self.INA_gain_0, self.INA_gain_1, self.INA_gain_2],
            enum = gain_enum,            
            linkedGet = _getGain,
            linkedSet = _setGain))

