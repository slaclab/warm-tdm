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


class FEAmplifier4(SaAmplifier):
    _model_ready = False

    @classmethod
    def _init_circuit_model(cls):
        if cls._model_ready:
            return

        # --- Symbols: bias network ---
        cls.sa_bias_out_p = sympy.symbols('sa_bias_out_p')
        cls.sa_bias_out_n = sympy.symbols('sa_bias_out_n')

        # --- Symbols: signal path nodes ---
        cls.sa_signal_out0_p = sympy.symbols('sa_signal_out0_p')
        cls.sa_signal_out0_n = sympy.symbols('sa_signal_out0_n')
        cls.sa_signal_out2_p = sympy.symbols('sa_signal_out2_p')
        cls.sa_signal_out2_n = sympy.symbols('sa_signal_out2_n')
        cls.sa_signal_out3_p = sympy.symbols('sa_signal_out3_p')
        cls.sa_signal_out3_n = sympy.symbols('sa_signal_out3_n')
        cls.sa_offset_p = sympy.symbols('sa_offset_p')
        cls.sa_offset_n = sympy.symbols('sa_offset_n')

        # --- Symbols: resistors ---
        cls.rf1 = sympy.symbols('rf1')
        cls.rg1 = sympy.symbols('rg1')
        cls.rf2 = sympy.symbols('rf2')
        cls.rgnd2 = sympy.symbols('rgnd2')
        cls.roff2 = sympy.symbols('roff2')
        cls.rf3 = sympy.symbols('rf3')
        cls.rg3 = sympy.symbols('rg3')
        cls.v = sympy.symbols('v')

        # --- Equations: Stage 1 instrumentation amp ---
        eq1 = sympy.Eq((cls.sa_signal_out0_p - cls.sa_bias_out_p) / cls.rf1,
                        (cls.sa_bias_out_p - cls.sa_bias_out_n) / cls.rg1)
        eq2 = sympy.Eq((cls.sa_signal_out0_n - cls.sa_bias_out_n) / cls.rf1,
                        (cls.sa_bias_out_n - cls.sa_bias_out_p) / cls.rg1)

        # --- Equations: Stage 2 offset summing amp ---
        eq3 = sympy.Eq((cls.sa_signal_out2_p - cls.sa_signal_out0_p) / cls.rf2,
                        cls.sa_signal_out0_p / cls.rgnd2 + (cls.sa_signal_out0_p - cls.sa_offset_p) / cls.roff2)
        eq4 = sympy.Eq((cls.sa_signal_out2_n - cls.sa_signal_out0_n) / cls.rf2,
                        cls.sa_signal_out0_n / cls.rgnd2 + (cls.sa_signal_out0_n - cls.sa_offset_n) / cls.roff2)

        # --- Equations: Stage 3 differential output amp ---
        eq5 = sympy.Eq((cls.sa_signal_out2_p - cls.v) / cls.rg3,
                        (cls.v - cls.sa_signal_out3_n) / cls.rf3)
        eq6 = sympy.Eq((cls.sa_signal_out2_n - cls.v) / cls.rg3,
                        (cls.v - cls.sa_signal_out3_p) / cls.rf3)

        eqs = [eq1, eq2, eq3, eq4, eq5, eq6]

        # --- Solve: inverse (output → input) ---
        inv_vars = [cls.sa_bias_out_p, cls.sa_bias_out_n,
                    cls.sa_signal_out0_p, cls.sa_signal_out0_n,
                    cls.sa_signal_out2_p, cls.sa_signal_out2_n]
        solutions = sympy.solve(eqs, inv_vars)
        cls.sa_bias_expr = sympy.simplify(solutions[cls.sa_bias_out_p] - solutions[cls.sa_bias_out_n])

        # --- Solve: forward (input → output) ---
        fwd_vars = [cls.sa_bias_out_p, cls.sa_bias_out_n,
                    cls.sa_signal_out0_p, cls.sa_signal_out0_n,
                    cls.sa_signal_out2_p, cls.sa_signal_out2_n,
                    cls.sa_signal_out3_p, cls.sa_signal_out3_n]
        solutions2 = sympy.solve(eqs, list(reversed(fwd_vars)))

        # --- Gain expressions ---
        out3 = sympy.simplify(solutions2[cls.sa_signal_out3_p] - solutions2[cls.sa_signal_out3_n])
        out2 = sympy.simplify(solutions2[cls.sa_signal_out2_p] - solutions2[cls.sa_signal_out2_n])
        out1 = sympy.simplify(solutions2[cls.sa_signal_out0_p] - solutions2[cls.sa_signal_out0_n])

        unity_input = {cls.sa_bias_out_p: .5, cls.sa_bias_out_n: -.5, cls.sa_offset_p: 0, cls.sa_offset_n: 0}
        cls.gain3_expr = (out3 / out2).subs(unity_input)
        cls.gain2_expr = (out2 / out1).subs(unity_input)
        cls.gain1_expr = out1.subs(unity_input)
        cls.offset_gain_expr = out3.subs({cls.sa_bias_out_p: 0, cls.sa_bias_out_n: 0,
                                          cls.sa_offset_p: .5, cls.sa_offset_n: -.5})

        cls._model_ready = True

    def __init__(self, **kwargs):
        self._init_circuit_model()
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'R_CABLE',
            description = 'Cable resistance on SA Bias',
            value = 120.0,
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
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain1_func()))

        self.add(pr.LinkVariable(
            name = 'GAIN_2',
            description = 'Second stage gain',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain2_func()))

        self.add(pr.LinkVariable(
            name = 'GAIN_3',
            description = 'Third stage gain',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain3_func()))

        self.add(pr.LinkVariable(
            name = 'OFFSET_GAIN',
            description = 'Overall gain of offset voltage',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.offset_gain_func()))


    def saBiasCurrent(self, saBiasDacVoltageP, saBiasDacVoltageN=0.0):
        vdiff = saBiasDacVoltageP * 2
        return vdiff / (self.R_CABLE.value() + (2*self.BIAS_SHUNT_R.value()))

    def saBiasDacVoltage(self, saBiasCurrent):
        resistance = self.R_CABLE.value() + (2*self.BIAS_SHUNT_R.value())
        voltage = saBiasCurrent * resistance

        # Start with both dacs at midpoint
        vp = (0.5 * voltage)
        vn = (0.5 * voltage)

        # Clip to the dac range
        vp = np.clip(vp, 0, 2.5)
        vn = 0.0

        return (vp, vn)


    def ampVin(self, vadc, voffsetP, voffsetN=0.0):
        ret = self.sa_bias_func(vadc/2, -vadc/2, voffsetP, -voffsetP)
        return ret

class AwaXeLna(SaAmplifier):
    _model_ready = False

    @classmethod
    def _init_circuit_model(cls):
        if cls._model_ready:
            return

        # --- Symbols: signal path ---
        cls.sa_signal_p = sympy.symbols('sa_signal_p')
        cls.sa_signal_n = sympy.symbols('sa_signal_n')

        # --- Symbols: LNA stage ---
        cls.lna_out_p = sympy.symbols('lna_out_p')
        cls.lna_out_n = sympy.symbols('lna_out_n')
        cls.lna_gain = sympy.symbols('awaxe_lna_gain')

        # --- Symbols: offset amp ---
        cls.sa_offset_p = sympy.symbols('sa_offset_p')
        cls.sa_offset_n = sympy.symbols('sa_offset_n')
        cls.offset_out_p = sympy.symbols('offset_out_p')
        cls.offset_out_n = sympy.symbols('offset_out_n')
        cls.rf2 = sympy.symbols('rf2')
        cls.roff2 = sympy.symbols('roff2')

        # --- Symbols: ADC amp ---
        cls.adc_p = sympy.symbols('adc_p')
        cls.adc_n = sympy.symbols('adc_n')
        cls.rf3 = sympy.symbols('rf3')
        cls.rg3 = sympy.symbols('rg3')
        cls.v = sympy.symbols('v')

        # --- Equations: Stage 1 LNA ---
        eq1 = sympy.Eq(cls.lna_out_p, cls.sa_signal_p * cls.lna_gain)
        eq2 = sympy.Eq(cls.lna_out_n, cls.sa_signal_n * cls.lna_gain)

        # --- Equations: Stage 2 offset amp ---
        eq3 = sympy.Eq((cls.offset_out_p - cls.lna_out_p) / cls.rf2,
                        (cls.lna_out_p - cls.sa_offset_p) / cls.roff2)
        eq4 = sympy.Eq((cls.offset_out_n - cls.lna_out_n) / cls.rf2,
                        (cls.lna_out_n - cls.sa_offset_n) / cls.roff2)

        # --- Equations: Stage 3 ADC differential amp ---
        eq5 = sympy.Eq((cls.offset_out_p - cls.v) / cls.rg3,
                        (cls.v - cls.adc_n) / cls.rf3)
        eq6 = sympy.Eq((cls.offset_out_n - cls.v) / cls.rg3,
                        (cls.v - cls.adc_p) / cls.rf3)

        eqs = [eq1, eq2, eq3, eq4, eq5, eq6]
        solve_vars = [cls.sa_signal_p, cls.sa_signal_n,
                      cls.lna_out_p, cls.lna_out_n,
                      cls.offset_out_p, cls.offset_out_n,
                      cls.adc_p, cls.adc_n]

        # --- Solve: inverse (ADC → signal input) ---
        solutions = sympy.solve(eqs, solve_vars)
        cls.sa_bias_expr = sympy.simplify(solutions[cls.sa_signal_p] - solutions[cls.sa_signal_n])

        # --- Solve: forward (signal input → ADC) ---
        solutions2 = sympy.solve(eqs, list(reversed(solve_vars)))

        adc_expr = sympy.simplify(solutions2[cls.adc_p] - solutions2[cls.adc_n])
        offset_stage_expr = sympy.simplify(solutions2[cls.offset_out_p] - solutions2[cls.offset_out_n])
        lna_expr = sympy.simplify(solutions2[cls.lna_out_p] - solutions2[cls.lna_out_n])

        # --- Gain expressions ---
        unity_input = {cls.sa_signal_p: .5, cls.sa_signal_n: -.5, cls.sa_offset_p: 0, cls.sa_offset_n: 0}
        cls.gain3_expr = (adc_expr / offset_stage_expr).subs(unity_input)
        cls.gain2_expr = (offset_stage_expr / lna_expr).subs(unity_input)
        cls.offset_gain_expr = adc_expr.subs({cls.sa_signal_p: 0, cls.sa_signal_n: 0,
                                              cls.sa_offset_p: .5, cls.sa_offset_n: -.5})

        cls._model_ready = True

    def __init__(self, **kwargs):
        """AwaXe LNA amplifier chain consists of AwaXe LNA
        followed by a unity gain stage to allow offset subtraction
        followed by the ADC amplifier"""
        self._init_circuit_model()
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'LNA_GAIN',
            value = 85.5))

        # Stage 2 Summing Differential Input Amplifier
        self.add(pr.LocalVariable(
            name = 'RF2',
            value = 100.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'ROFF2',
            value = 100.0,
            units = u'\u03a9'))

        # Stage 3 Differential Amplifier
        self.add(pr.LocalVariable(
            name = 'RF3',
            value = 825.0,
            units = u'\u03a9'))

        self.add(pr.LocalVariable(
            name = 'RG3',
            value = 1.0e3,
            units = u'\u03a9'))

        sa_vars = [
            self.LNA_GAIN,
            self.RF2,
            self.ROFF2,
            self.RF3,
            self.RG3]

        def setConversions():
            resistors = {
                self.lna_gain: self.LNA_GAIN.value(),
                self.rf2: self.RF2.value(),
                self.roff2 : self.ROFF2.value(),
                self.rf3: self.RF3.value(),
                self.rg3: self.RG3.value()}

            self.sa_bias_func = sympy.lambdify([self.adc_p, self.adc_n, self.sa_offset_p, self.sa_offset_n],
                                               self.sa_bias_expr.subs(resistors),
                                               'numpy')

            g3=  self.gain3_expr.subs(resistors)
            g2=  self.gain2_expr.subs(resistors)

            self.gain3_func = sympy.lambdify([], self.gain3_expr.subs(resistors), 'numpy')
            self.gain2_func = sympy.lambdify([], self.gain2_expr.subs(resistors), 'numpy')
            self.gain1_func = lambda: self.LNA_GAIN.value()
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
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain1_func()))

        self.add(pr.LinkVariable(
            name = 'GAIN_2',
            description = 'Second stage gain',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain2_func()))

        self.add(pr.LinkVariable(
            name = 'GAIN_3',
            description = 'Third stage gain',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.gain3_func()))

        self.add(pr.LinkVariable(
            name = 'OFFSET_GAIN',
            description = 'Overall gain of offset voltage',
            mode = 'RO',
            disp = '{:0.3f}',
            dependencies = [self.Conv],
            linkedGet = lambda read: self.offset_gain_func()))


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
            value = 120.0,
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

        self.add(pr.LinkVariable(
            name = 'MaxCurrent',
            dependencies = [self.FilterR, self.ShuntR, self.CableR, self.FbR, self.InputR, self.IOUTFS, self.FSADJ],
            units = '\u03bcA',
            mode = 'RO',
            disp = '{:0.3f}',
            linkedGet = self.maxCurrent))

        self.add(pr.LinkVariable(
            name = 'MinCurrent',
            dependencies = [self.FilterR, self.ShuntR, self.CableR, self.FbR, self.InputR, self.IOUTFS, self.FSADJ],
            units = '\u03bcA',
            mode = 'RO',
            disp = '{:0.3f}',
            linkedGet = self.minCurrent))


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
        gain = self.gain()
        load = self.LoadR.value()
        ioutfs = self.IOUTFS.value()
        vin = voltage / gain
        iin = vin / load
        iina = (iin + ioutfs) / 2 # Offset binary
        dac =  int((iina / ioutfs) * 16384)
        if dac > 16383:
            dac = 16383
        if dac < 0:
            dac = 0
        return int(dac)

    def outCurrentToDac(self, current):
        vout = current * 1e-6 * self.rout()
        return self.outVoltageToDac(vout)

    def dacToLoadVoltage(self, dac):
        voltage = self.dacToOutVoltage(dac)
        load = voltage * (self.CableR.value() / self.OutR.value())
        return load

    def maxCurrent(self):
        return self.dacToOutCurrent(16383)

    def minCurrent(self):
        return self.dacToOutCurrent(0)


class FastDacAmplifierDiff(FastDacAmplifierSE):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def gain(self):
        return (1 + (self.FbR.value() / self.InputR.value()))

    def rout(self):
        return (2 * self.FilterR.value()) + (2 * self.ShuntR.value()) + self.CableR.value()

class AwaXeTesBiasAmp(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'Type',
            mode = 'RO',
            value = self.__class__.__name__))

        self.add(pr.LocalVariable(
            name = '2X',
            value = False))

    def outCurrentToDac(self, current, delatch):
        # For now only allow 0-1.8mA
        iout = current * 1.0e6
        if iout > 1.8e3:
            iout = 1.8e3
        if iout < 0:
            iout = 0.0

        dac = (iout / 1.8e3) * 256
        return (dac, 0)


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
            value = 120.0,
            units = '\u03A9'))


    def outCurrentToDac(self, current, delatch):
        iout = current * 1.0e-6
        iout = iout if self.Invert.value() == False else iout * -1.0

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

        v1 = 2 * iout * gainR

        # Start with both dacs at midpoint
        dacVp = 1.25 + (0.5 * v1)
        dacVn = 1.25 - (0.5 * v1)

        # Clip to the dac range
        dacVp = np.clip(dacVp, 0, 2.5)
        dacVn = np.clip(dacVn, 0, 2.5)

        return (dacVp, dacVn)


    def dacToOutCurrent(self, dacVp, dacVn, delatch):
        # First stage amp has gain 1
        v1 = dacVp - dacVn

        # input to second stage is half v1
        v2 = 0.5 * v1

        gainR = self.GainR.value()

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

        # Clip vout to amplifier rails
        vout = np.clip(vout, -5.0, 5.0)

        # Calculate output current
        iout = (v2 - vout) / totalR
        iout = iout * 1.0e6
        iout = iout if self.Invert.value() == False else iout * -1.0

        return iout
