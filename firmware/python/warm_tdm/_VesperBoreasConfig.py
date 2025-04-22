import pyrogue as pr
import numpy as np

class VectorLinkVariable(pr.LinkVariable):
    def __init__(self, **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            **kwargs)

    def _get(self, read):
        with self.root.updateGroup():
            gain = 0
            for dep in reversed(self.dependencies):
                gain <<= 1                
                gain |= dep.get(read=read)
                
            return gain #gain_enum[gain]

    def _set(self, value, write):
        with self.root.updateGroup():
            for pos, dep in enumerate(self.dependencies):
                dep.set(value=(value>>pos)&1, write=write)

class VesperBoreasConfig(pr.Device):
    def __init__(self, frontEnd, saBiasDac, saOffsetDac, tesBiasDac, saFbDac, sq1BiasDac, sq1FbDac, auxDac, **kwargs):

        super().__init__(**kwargs)

        self._amps = [frontEnd.Channel[x].SAAmp for x in range(8)]

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
                    enum = {0: '0',
                            1: '1'},
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
                print(f'Warning! DAC value for {self.path} ({v}) does not corespond to FastDacOn ({on.value()}) or FastDacOff ({off.value()})')
                return 0

                 

        # SA FB DAC Variables
        self.add(FastDacLinkVariable(
            name = 'INA_gain_0',
            hidden = True,
            dac = saFbDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'INA_gain_1',
            hidden = True,            
            dac = auxDac.OverrideRaw[2]))

        self.add(FastDacLinkVariable(
            name = 'INA_gain_2',
            hidden = True,            
            dac = sq1BiasDac.OverrideRaw[6]))


        self.add(VectorLinkVariable(
            name = 'GAIN',
            dependencies = [self.INA_gain_0, self.INA_gain_1, self.INA_gain_2],
            enum = {
                0: '20',
                1: '50',
                2: '100',
                3: '150',
                4: '200',
                5: '300',
                6: '600'}))

        def ampUpdate(path, varValue):
            # Update the gain in amplifier model whenever it changes here
            for col in range(4, 8):
                self._amps[col].CRYO_AMP_GAIN.set(float(self.GAIN.valueDisp()))

        self.GAIN.addListener(ampUpdate)

        self.add(FastDacLinkVariable(
            name = 'INA_sel',
            dac = auxDac.OverrideRaw[3]))
        
        self.add(FastDacLinkVariable(
            name = 'EN_INA',
            dac = sq1FbDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'EN_BLK_INA',
            dac = auxDac.OverrideRaw[1]))

        self.add(FastDacLinkVariable(
            name = 'Chicken',
            dac = sq1FbDac.OverrideRaw[7]))
        
        self.add(FastDacLinkVariable(
            name = 'Gallo_INA',
            dac = auxDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'Iref_sel_0',
            hidden = True,
            dac = sq1BiasDac.OverrideRaw[7]))

        self.add(FastDacLinkVariable(
            name = 'Iref_sel_1',
            hidden = True,            
            dac = auxDac.OverrideRaw[6]))
        
        self.add(VectorLinkVariable(
            name = 'Iref_sel',
            dependencies = [self.Iref_sel_0, self.Iref_sel_1],
            enum = {
                0: '00',
                1: '01',
                2: '10',
                3: '11'}))


        self.add(FastDacLinkVariable(
            name = 'I_cntrl_b0',
            hidden = True,
            dac = sq1FbDac.OverrideRaw[6]))

        self.add(FastDacLinkVariable(
            name = 'I_cntrl_b1',
            hidden = True,            
            dac = auxDac.OverrideRaw[4]))

        self.add(FastDacLinkVariable(
            name = 'I_cntrl_b2',
            hidden = True,            
            dac = saFbDac.OverrideRaw[7]))
        
        self.add(VectorLinkVariable(
            name = 'I_cntrl_b',
            dependencies = [self.I_cntrl_b0, self.I_cntrl_b1, self.I_cntrl_b2],
            enum = {k: f'{k:03b}' for k in range(8)}))
        
        
        self.add(FastDacLinkVariable(
            name = 'I_cntrl_c0',
            hidden = True,            
            dac = sq1BiasDac.OverrideRaw[5]))

        self.add(FastDacLinkVariable(
            name = 'I_cntrl_c1',
            hidden = True,            
            dac = auxDac.OverrideRaw[0]))

        self.add(FastDacLinkVariable(
            name = 'I_cntrl_c2',
            hidden = True,            
            dac = auxDac.OverrideRaw[7]))

        self.add(VectorLinkVariable(
            name = 'I_cntrl_c',
            dependencies = [self.I_cntrl_c0, self.I_cntrl_c1, self.I_cntrl_c2],
            enum = {k: f'{k:03b}' for k in range(8)}))
        

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

