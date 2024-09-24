import pyrogue as pr
import numpy as np
import sympy

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

#         self.add(pr.LinkVariable(
#             name = 'OffsetGain',
#             disp = '{:0.3f}',
#             mode = 'RO',
#             dependencies = sa_vars,
#             linkedGet = lambda read: (1-0.9) / (self.ampVin(0.0, 1.0)-self.ampVin(0.0, 0.9))))
            


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
        return (saBiasCurrent * self.SA_BIAS_SHUNT_R.value(), 0)

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
        return (voltage, 0)

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

class FEAmplifier4(SaAmplifier):

    # Declare schematic nets and resistors
    sa_bias_dac_p = sympy.symbols('sa_bias_dac_p')
    sa_bias_dac_n = sympy.symbols('sa_bias_dac_n')
    sa_bias_dac_cm = sympy.symbols('sa_bias_dac_cm')
    sa_bias_dac_diff = sympy.symbols('sa_bias_dac_diff')
    sa_bias_shunt_r = sympy.symbols('sa_bias_shunt_r')
    sa_bias_cable_r = sympy.symbols('sa_bias_cable_r')
    sa_bias_squid_r = sympy.symbols('sa_bias_squid_r')

    sa_bias_out_p = sympy.symbols('sa_bias_out_p')
    sa_bias_out_n = sympy.symbols('sa_bias_out_n')
    sa_bias_out_diff = sympy.symbols('sa_bias_out_diff')
    sa_bias_current = sympy.symbols('sa_bias_current')
    sa_signal_out0_p = sympy.symbols('sa_signal_out0_p')
    sa_signal_out0_n = sympy.symbols('sa_signal_out0_n')
    sa_signal_out1_p = sympy.symbols('sa_signal_out1_p')
    sa_signal_out1_n = sympy.symbols('sa_signal_out1_n')
    sa_offset_p = sympy.symbols('sa_offset_p')
    sa_offset_n = sympy.symbols('sa_offset_n')
    sa_signal_out2_p = sympy.symbols('sa_signal_out2_p')
    sa_signal_out2_n = sympy.symbols('sa_signal_out2_n')
    sa_signal_out3_p = sympy.symbols('sa_signal_out3_p')
    sa_signal_out3_n = sympy.symbols('sa_signal_out3_n')


    # Stage 1 Resistors
    rf1 = sympy.symbols('rf1')
    rg1 = sympy.symbols('rg1')

    # Stage 2 Resistors
    rf2 = sympy.symbols('rf2') # Feedback
    rgnd2 = sympy.symbols('rgnd2') 
    rin2 = sympy.symbols('rin2')
    roff2 = sympy.symbols('roff2')

    # Stage 3 Resistors
    rf3 = sympy.symbols('rf3')
    rg3 = sympy.symbols('rg3')
    v = sympy.symbols('v')

    # Stage 1 instrumentation amp equations
    eq1 = sympy.Eq((sa_signal_out0_p-sa_bias_out_p)/rf1, (sa_bias_out_p-sa_bias_out_n)/rg1)
    eq2 = sympy.Eq((sa_signal_out0_n-sa_bias_out_n)/rf1, (sa_bias_out_n-sa_bias_out_p)/rg1)

    # Stage 2 differential amp equations
    eq3 = sympy.Eq((sa_signal_out2_p-sa_signal_out0_p)/rf2, sa_signal_out0_p/rgnd2 + (sa_signal_out0_p-sa_offset_p)/roff2)
    eq4 = sympy.Eq((sa_signal_out2_n-sa_signal_out0_n)/rf2, sa_signal_out0_n/rgnd2 + (sa_signal_out0_n-sa_offset_n)/roff2)

    # Stage 3 differential amp equations
    eq5 = sympy.Eq((sa_signal_out2_p-v)/rg3, (v-sa_signal_out3_n)/rf3)
    eq6 = sympy.Eq((sa_signal_out2_n-v)/rg3, (v-sa_signal_out3_p)/rf3)


    solve_vars =  [sa_bias_out_p, sa_bias_out_n, sa_signal_out0_p, sa_signal_out0_n,
                   sa_signal_out2_p, sa_signal_out2_n, sa_signal_out3_p, sa_signal_out3_n]

    solutions = sympy.solve([eq1, eq2, eq3, eq4, eq5, eq6], [sa_bias_out_p, sa_bias_out_n, sa_signal_out0_p, sa_signal_out0_n, sa_signal_out2_p, sa_signal_out2_n])

    # Expression for sa_bias_out (differential) given sa_signal_out3 and voffset
    sa_bias_expr = sympy.simplify(solutions[sa_bias_out_p]-solutions[sa_bias_out_n])

    solutions2 = sympy.solve([eq1, eq2, eq3, eq4, eq5, eq6], list(reversed(solve_vars)))

    # Expressions to compute gain of each stage
    sa_signal_out3_expr = sympy.simplify(solutions2[sa_signal_out3_p]-solutions2[sa_signal_out3_n])
    sa_signal_out2_expr = sympy.simplify(solutions2[sa_signal_out2_p]-solutions2[sa_signal_out2_n])
    sa_signal_out1_expr = sympy.simplify(solutions2[sa_signal_out0_p]-solutions2[sa_signal_out0_n])        

    gain3_expr = (sa_signal_out3_expr/sa_signal_out2_expr).subs({sa_bias_out_p:.5, sa_bias_out_n:-.5, sa_offset_p:0, sa_offset_n:0})
    gain2_expr = (sa_signal_out2_expr/sa_signal_out1_expr).subs({sa_bias_out_p:.5, sa_bias_out_n:-.5, sa_offset_p:0, sa_offset_n:0})
    gain1_expr = (sa_signal_out1_expr).subs({sa_bias_out_p:.5, sa_bias_out_n:-.5, sa_offset_p:0, sa_offset_n:0})
    offset_gain_expr = sa_signal_out3_expr.subs({sa_bias_out_p:0, sa_bias_out_n:0, sa_offset_p:.5, sa_offset_n:-.5})    

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'R_CABLE',
            description = 'Cable resistance on SA Bias',
            value = 200.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'BIAS_SHUNT_R',
            description = 'Shunt resistance on high side of SA Bias',
            value = 10e3 + 4.990e3,
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
            value = 40.2,
            units = u'\u03a9'))

        # Stage 2 Summing Differential Input Amplifier
        self.add(pr.LocalVariable(
            name = 'RF2',
            value = 100.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'ROFF2',
            value = 402.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'RGND2',
            value = 21.0,
            units = u'\u03a9'))


        # Stage 3 Differential Amplifier
        self.add(pr.LocalVariable(
            name = 'RF3',
            value = 3.66e3,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'RG3',
            value = 1.0e3,
            units = u'\u03a9'))

        sa_vars = [
            self.RF1,
            self.RG1,
            self.RF2,
            self.ROFF2,
            self.RGND2,
            self.RF3,
            self.RG3]

        def setConversions():
            resistors = {
                self.rf1: self.RF1.value(),
                self.rg1: self.RG1.value(),
                self.rf2: self.RF2.value(),
                self.rgnd2: self.RGND2.value(),
                self.roff2 : self.ROFF2.value(),
                self.rf3: self.RF3.value(),
                self.rg3: self.RG3.value()}

            self.sa_bias_func = sympy.lambdify([self.sa_signal_out3_p, self.sa_signal_out3_n, self.sa_offset_p, self.sa_offset_n],
                                               self.sa_bias_expr.subs(resistors),
                                               'numpy')
            
            g3=  self.gain3_expr.subs(resistors)
            g2=  self.gain2_expr.subs(resistors)
            g1=  self.gain1_expr.subs(resistors)

            self.gain3_func = sympy.lambdify([], self.gain3_expr.subs(resistors), 'numpy')
            self.gain2_func = sympy.lambdify([], self.gain2_expr.subs(resistors), 'numpy')
            self.gain1_func = sympy.lambdify([], self.gain1_expr.subs(resistors), 'numpy')
            self.offset_gain_func = sympy.lambdify([], self.offset_gain_expr.subs(resistors), 'numpy')                        
            return 0
        
        setConversions()

        self.add(pr.LinkVariable(
            name = 'Conv',
            dependencies = sa_vars,
            hidden = True,
            linkedGet = setConversions))

        self.addGainVars(sa_vars)

        self.add(pr.LinkVariable(
            name = 'GAIN_1',
            description = 'First stage gain',
            mode = 'RO',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain1_func()))

        self.add(pr.LinkVariable(
            name = 'GAIN_2',
            description = 'Second stage gain',
            mode = 'RO',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain2_func()))
            
        self.add(pr.LinkVariable(
            name = 'GAIN_3',
            description = 'Third stage gain',
            mode = 'RO',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain3_func()))

        self.add(pr.LinkVariable(
            name = 'OFFSET_GAIN',
            description = 'Overall gain of offset voltage',
            mode = 'RO',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.offset_gain_func()))
                                                        

    def saBiasCurrent(self, saBiasDacVoltageP, saBiasDacVoltageN=0.0):
        #vdiff = saBiasDacVoltageP + saBiasDacVoltageN # Invert negative side
        vdiff = saBiasDacVoltageP * 2 # Invert P to double the voltage
        return vdiff / (self.R_CABLE.value() + (2*self.BIAS_SHUNT_R.value()))

    def saBiasDacVoltage(self, saBiasCurrent):
        resistance = self.R_CABLE.value() + (2*self.BIAS_SHUNT_R.value())
        voltage = saBiasCurrent * resistance

        # Start with both dacs at midpoint
        vp = (0.5 * voltage)
        vn = (0.5 * voltage)

        # Clip to the dac range
        vp = np.clip(vp, 0, 2.5)
        vn = 0.0#vn = np.clip(vn, 0, 2.5)

        return (vp, vn)


    def ampVin(self, vadc, voffsetP, voffsetN=0.0):
        ret = self.sa_bias_func(vadc/2, -vadc/2, voffsetP, -voffsetP)
        return ret


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
        #print(f'{self.path}.dacToOutVoltage({dac=})')
        iOutFs = self.IOUTFS.value()
        iOutA = (dac/16384) * iOutFs
        iOutB = ((16383-dac)/16384) * iOutFs
        dacCurrent = (iOutA, iOutB)

        gain = self.gain()
        load = self.LoadR.value()

        vin = [iOutA * load, iOutB * load]

        vout = (vin[0] - vin[1]) * gain
        #print(f'{gain=}, {load=}, {iOutFs=}, {vin=}, {dacCurrent=}')
        return vout

    def dacToOutCurrent(self, dac):
        """ Calculate output current in uA """
        vout = self.dacToOutVoltage(dac)
        iout = vout / self.rout()
        return iout * 1e6

    def outVoltageToDac(self, voltage):
        #print(f'{self.path}.outVoltageToDac({voltage=})')
        gain = self.gain()
        load = self.LoadR.value()
        ioutfs = self.IOUTFS.value()
        vin = voltage / gain
        iin = vin / load
        iina = (iin + ioutfs) / 2
        dac =  int((iina / ioutfs) * 16384)
        #print(f'{gain=}, {load=}, {ioutfs=}, {vin=}, {iin=}, {iina=}, {dac=}')
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
        return (1 + (self.FbR.value() / self.InputR.value()))

    def rout(self):
        return (2 * self.FilterR.value()) + (2 * self.ShuntR.value()) + self.CableR.value()
    
class TesBiasAmpC00(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'Type',
            mode = 'RO',
            value = self.__class__.__name__))

        self.add(pr.LocalVariable(
            name = 'Invert',
            value = False,
            mode = 'RO'))

        self.add(pr.LocalVariable(
            name = 'GainR',
            value = 1.0e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'DelatchR',
            value = 174.0,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'Filter1R',
            value = 800.0,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'Filter2R',
            value = 200.0,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'CableR',
            value = 174.0,
            units = '\u03A9'))


    def outCurrentToDac(self, current, delatch):
        #print(f'{self.path}.outCurrentToDac({current=}, {delatch=})')

        iout = current * 1.0e-6
        iout = iout if self.Invert.value() == False else iout * -1.0
        #print(f'{iout=}')

        if delatch is False:
            gainR = self.GainR.value()
            filterR = self.Filter1R.value() + self.Filter2R.value()
        else:
            # Calculate parallel resistance
            gainR = self.GainR.value()
            delatchR = self.DelatchR.value()
            gainR = (gainR * delatchR) / (gainR + delatchR)

            # Delatch has only second filter
            filterR = self.Filter2R.value()


        #print(f'{gainR=}')

        v1 = 2 * iout * gainR
        #print(f'{v1=}')

        # Start with both dacs at midpoint
        dacVp = 1.25 + (0.5 * v1)
        dacVn = 1.25 - (0.5 * v1)

        # Clip to the dac range
        dacVp = np.clip(dacVp, 0, 2.5)
        dacVn = np.clip(dacVn, 0, 2.5)

        #print(f'{dacVp=}, {dacVn=}')

        return (dacVp, dacVn)


    def dacToOutCurrent(self, dacVp, dacVn, delatch):
        #print(f'{self.path}.dacToOutCurrent({dacVp=}, {dacVn=}, {delatch=})')

        # First stage amp has gain 1
        v1 = dacVp - dacVn
        #print(f'{v1=}')

        # input to second stage is half v1
        v2 = 0.5 * v1
        #print(f'{v2=}')

        gainR = self.GainR.value()
        #print(f'{gainR=}')

        if delatch is False:
            gainR = self.GainR.value()
            filterR = self.Filter1R.value() + self.Filter2R.value()
        else:
            # Calculate parallel resistance
            gainR = self.GainR.value()
            delatchR = self.DelatchR.value()
            gainR = (gainR * delatchR) / (gainR + delatchR)

            # Delatch has only second filter
            filterR = self.Filter2R.value()

        # Calculate Vout needed to drive the current
        totalR = filterR + self.CableR.value()
        vout = -0.5 * v1 * (totalR / gainR - 1)

        #print(f'{totalR=}')
        #print(f'{vout=}')

        # Clicp vout to amplifier rails
        vout = np.clip(vout, -5.0, 5.0)

        #print(f'Clipped {vout=}')

        # Calculate output current
        iout = (v2 - vout) / totalR
        iout = iout * 1.0e6
        iout = iout if self.Invert.value() == False else iout * -1.0

        #print(f'{iout=}')
        return iout
