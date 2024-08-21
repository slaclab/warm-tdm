import pyrogue as pr

class SaAmplifier(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'Type',
            mode = 'RO',
            value = self.__class__.__name__))
        

    def addGainVars(self, sa_vars):

        self.add(pr.LinkVariable(
            name = 'AmpInConvFactor',
            units = u'\u03bcV/ADC',
            disp = '{:0.3f}',
            mode = 'RO',
            dependencies = sa_vars,
            linkedGet = lambda read: 1.0e6 * (self.ampVin(2/2**13, 0.0)-self.ampVin(1/2**13, 0.0))))

        self.add(pr.LinkVariable(
            name = 'AmpSaGain',
            disp = '{:0.3f}',
            mode = 'RO',
            dependencies = sa_vars,
            linkedGet = lambda read: (1-0.9) / (self.ampVin(1.0, 0.0)-self.ampVin(0.9, 0.0))))


class ColumnBoardC00SaAmp(SaAmplifier):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
            value = 11))
        
        self.add(pr.LocalVariable(
            name = 'SA_AMP_GAIN_3',
            value = 1.0))
        
        sa_vars = [
            self.SA_BIAS_SHUNT_R,
            self.SA_OFFSET_R,
            self.SA_AMP_FB_R,
            self.SA_AMP_GAIN_R,
            self.SA_AMP_GAIN_2,
            self.SA_AMP_GAIN_3]

        self.addGainVars(sa_vars)

    def saBiasCurrent(self, saBiasDacVoltageP, saBiasDacVoltageN=0.0):
        return saBiasDacVoltageP / self.SA_BIAS_SHUNT_R.value()

    def saBiasDacVoltage(self, saBiasCurrent):
        return saBiasCurrent * self.SA_BIAS_SHUNT_R.value()
        
    def ampVin(self, vout, voffsetP, voffsetN=0):
        """Calculate SA_OUT an amplifier input given amp output and voffset"""

        G_OFF = 1.0/self.SA_OFFSET_R.value()
        G_FB = 1.0/self.SA_AMP_FB_R.value()
        G_GAIN = 1.0/self.SA_AMP_GAIN_R.value()

        V_OUT_1 = vout/(self.SA_AMP_GAIN_2.value()*self.SA_AMP_GAIN_3.value())

        SA_OUT = ((G_OFF * voffsetP) + (G_FB * V_OUT_1)) / (G_OFF + G_FB + G_GAIN)

        return SA_OUT


class FEAmplifier3(SaAmplifier):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'R_CABLE',
            description = 'Cable resistance on SA Bias',
            value = 100.0,
            units = u'\u03a9'))
        
        self.add(pr.LocalVariable(
            name = 'BIAS_SHUNT_R_P',
            description = 'Shunt resistance on high side of SA Bias',
            value = 10e3 + 4.990e3,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'BIAS_SHUNT_R_N',
            description = 'Shunt resistance on low side of SA bias',
            value = 100.0,
            units = u'\u03a9'))            


        # Stage 1 Instrumentation Amplifier
        # RF1 = R34/R33
        # RG1 = R6
        self.add(pr.LocalVariable(
            name = 'RF1',
            description = 'R33 and R34',
            value = 100.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'RG1',
            description = 'R6',
            value = 18.20,
            units = u'\u03a9'))

        #self.RF1 = 100.0
        #self.RG1 = 18.20

        self.add(pr.LinkVariable(
            name = 'GAIN_1',
            description = 'First stage gain',
            mode = 'RO',
            dependencies = [self.RF1, self.RG1],
            linkedGet = lambda read: 1 + (( 2 * self.RF1.get(read=read)) / self.RG1.get(read=read))))

        self.add(pr.LocalVariable(
            name = 'BIAS_DAC_N',
            description = 'Voltage developed at SA_BIAS_IN_RET_SQ1B',
            value = 50.0e-3,
            units = 'V'))


        # Stage 2 Summing Differential Input Amplifier
        self.add(pr.LocalVariable(
            name = 'RF2',
            description = 'R35',
            value = 100.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'RG2',
            description = 'R15 and R17',
            value = 33.2,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'R_OFFSET',
            description = 'R16',
            value = 402.0,
            units = u'\u03a9'))
        
        #self.RF2 = 100.0
        #self.RG2 = 33.2
        #self.ROFF = 33.2 # Offset gain

        self.add(pr.LocalVariable(
            name = 'GAIN_COLUMN',
            description = 'Gain of final amplification state on Column board',
            value = 3.67))

        sa_vars = [
            self.R_CABLE,
            self.BIAS_SHUNT_R_P,
            self.BIAS_SHUNT_R_N,
            self.RF1,
            self.RG1,
            self.GAIN_1,
            self.BIAS_DAC_N,
            self.RF2,
            self.RG2,
            self.R_OFFSET,
            self.GAIN_COLUMN]

        self.addGainVars(sa_vars)        

        
    def saBiasCurrent(self, saBiasDacVoltageP, saBiasDacVoltageN=0.0):
        vdiff = saBiasDacVoltageP - (saBiasDacVoltageN + self.BIAS_DAC_N.value())
        return vdiff / (self.R_CABLE.value() + self.BIAS_SHUNT_R_P.value() + self.BIAS_SHUNT_R_N.value())

    def saBiasDacVoltage(self, saBiasCurrent):
        resistance = self.R_CABLE.value() + self.BIAS_SHUNT_R_P.value() + self.BIAS_SHUNT_R_N.value()
        voltage = saBiasCurrent * resistance
        # apply neg offset
        voltage = voltage + self.BIAS_DAC_N.value()
        return voltage

    def ampVout(self, vin, voffset):
        # Make it more readable
        RF2 = self.RF2
        RG2 = self.RG2
        ROFF = self.ROFF
        
        # Gain of stage 1 Intrumentation Amplifier    
        gain1 = self.GAIN_1

        # Differential stage 1 voltage
        v1p = (vin * gain1) / 2
        v1n = -(vin * gain1) / 2

        # Stage 2 positive amp terminal voltage
        v2 = v1p * self.RF2 / (self.RG2 + self.RF2)

        # Stage 2 output voltage
        # Ugly equation from wolfram alpha
        vout2 = (RF2 * ( RF2 * RG2 * (v1p - 2 * voffset) + 2 * RF2 * v1p * ROFF + 2 * RG2 * (v1p * ROFF - RG2 * voffset))) / (2 * RG2 * ROFF * (RF2 + RG2))
        #vout2 = self.RF2 * ((self.GOFF * voffset) - (self.GOFF * v2) + (self.GF2 * v2) - (self.GG2 * v1n) + (self.GG2 * v2))

        # Final output voltage after column board amplifiers
        vout = vout2 * self.GAIN_COLUMN

        return vout
                           

    def ampVin(self, vadc, voffsetP, voffsetN=0.0):
        #print(f'ampVin({vadc=}, {voffsetP=})')
        RF2 = self.RF2.value()
        RG2 = self.RG2.value()
        ROFF = self.R_OFFSET.value()

        vout2 = vadc / self.GAIN_COLUMN.value()

        # Ugly equation from wolfram alpha
        v1p = (2 * RG2 * (RF2 + RG2) * (RF2 * voffsetP + vout2 * ROFF)) / (RF2 * (RF2 * (RG2 - (2 * ROFF)) - (2 * RG2 * ROFF)))
        v1p = -1.0 * v1p

        #v1 = v1p - v1n
        vnn = self.BIAS_DAC_N.value()

        vin = (v1p + (vnn * self.GAIN_1.value())) / self.GAIN_1.value()

        #vin = vin - self.BIAS_DAC_N.value() # Not sure this is right

        return vin
        
    
class FastDacAmplifierSE(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'Type',
            mode = 'RO',
            value = self.__class__.__name__))
        
        self.add(pr.LocalVariable(
            name = 'FSADJ',
            value = 2.0e3,
            units = '\u03A9'))

        self.add(pr.LinkVariable(
            name = 'IOUTFS',
            units = 'A',
            linkedGet = lambda: 1.2 / self.FSADJ.value() * 32))

        self.add(pr.LocalVariable(
            name = 'Invert',
            value = False,))

        self.add(pr.LocalVariable(
            name = 'LoadR',
            value = 24.9,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'InputR',
            value = 1.0e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'FbR',
            value = 4.02e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'FilterR',
            value = 49.9 * 3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'ShuntR',
            value = 1.0e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'CableR',
            value = 100.0,
            units = '\u03A9'))

        self.add(pr.LinkVariable(
            name = 'Gain',
            dependencies = [self.FbR, self.InputR],
            linkedGet = self.gain))

        self.add(pr.LinkVariable(
            name = 'OutR',
            dependencies = [self.FilterR, self.ShuntR, self.CableR],
            units = '\u03A9',
            linkedGet = self.rout))

    def gain(self):
        ret = self.FbR.value() / (self.InputR.value())
        if self.Invert.value() is True:
            ret = ret * -1
        return ret

    def rout(self):
        return self.FilterR.value() + self.ShuntR.value() + self.CableR.value()

    def dacToOutVoltage(self, dac):
        iOutFs = self.IOUTFS.value()
        iOutA = (dac/16384) * iOutFs
        iOutB = ((16383-dac)/16384) * iOutFs
        dacCurrent = (iOutA, iOutB)

        gain = self.gain()
        load = self.LoadR.value()

        vin = [iOutA * load, iOutB * load]

        vout = (vin[0] - vin[1]) * gain
        return vout

    def dacToOutCurrent(self, dac):
        """ Calculate output current in uA """
        vout = self.dacToOutVoltage(dac)
        iout = vout / self.rout()
        return iout * 1e6

    def outVoltageToDac(self, voltage):
#        print(f'outVoltageToDac({voltage=})')
        gain = self.gain()
        load = self.LoadR.value()
        ioutfs = self.IOUTFS.value()
        vin = voltage / gain
        iin = vin / load
        iina = (iin + ioutfs) / 2
        dac =  int((iina / ioutfs) * 16384)
#        print(f'{gain=}, {load=}, {ioutfs=}, {vin=}, {iin=}, {iina=}, {dac=}')
        return int(dac)

    def outCurrentToDac(self, current):
        vout = current * 1e-6 * self.rout()
        return self.outVoltageToDac(vout)

    def dacToLoadVoltage(self, dac):
        voltage = self.dacToOutVoltage(dac)
        load = voltage * (self.CableR.value() / self.OutR.value())
        return load


class FastDacAmplifierDiff(FastDacAmplifierSE):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def gain(self):
        return 2 * self.FbR.value() / self.InputR.value()

    def rout(self):
        return (2 * self.FilterR.value()) + (2 * self.ShuntR.value()) + self.CableR.value()

    
