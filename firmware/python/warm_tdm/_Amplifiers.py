import pyrogue as pr

class SaAmplifier(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def addGainVars(self, sa_vars):
        
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


class ColumnBoardC00SaAmp(SaAmplifier):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        
        sa_vars = [
            self.SA_OFFSET_R,
            self.SA_AMP_FB_R,
            self.SA_AMP_GAIN_R,
            self.SA_AMP_GAIN_2,
            self.SA_AMP_GAIN_3]

        self.addGainVars(sa_vars)


        
    def ampVin(self, vout, voffset):
        """Calculate SA_OUT an amplifier input given amp output and voffset"""

        G_OFF = 1.0/self.SA_OFFSET_R.value()
        G_FB = 1.0/self.SA_AMP_FB_R.value()
        G_GAIN = 1.0/self.SA_AMP_GAIN_R.value()

        V_OUT_1 = vout/(self.SA_AMP_GAIN_2.value()*self.SA_AMP_GAIN_3.value())

        SA_OUT = ((G_OFF * voffset) + (G_FB * V_OUT_1)) / (G_OFF + G_FB + G_GAIN)

        return SA_OUT


class FEAmplifier3(SaAmplifier):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Make these into variables

        # Stage 1 Instrumentation Amplifier
        # RF1 = R34/R33
        # RG1 = R6
        self.RF1 = 100.0
        self.RG1 = 18.20


        self.GAIN_1 = 1 + (( 2 * self.RF1) / self.RG1 )

        # Stage 2 Summing Differential Input Amplifier
        self.RF2 = 100.0
        self.RG2 = 33.2
        self.ROFF = 33.2 # Offset gain

        self.GAIN_COLUMN = 3.67
        

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
                           

    def ampVin(self, vadc, voffset):

        RF2 = self.RF2
        RG2 = self.RG2
        ROFF = self.ROFF

        vout2 = vadc / self.GAIN_COLUMN
        

        # Ugly equation from wolfram alpha
        v1p = (2 * RG2 * (RF2 + RG2) * (RF2 * voffset + vout2 * ROFF)) / (RF2 * (RF2 * (RG2 - (2 * ROFF)) - (2 * RG2 * ROFF)))
        v1p = -1.0 * v1n

        v1 = v1p - v1n

        vin = v1 / self.GAIN_1

        return vin
        
    
class FastDacAmplifierSE(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

    
