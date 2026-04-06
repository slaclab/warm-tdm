"""
TES Bias Waveform Generator

This module provides a TES bias waveform generator to create various waveforms for testing and characterization purposes.

The `TesBiasWaveformProcess` class is the main entry point for generating waveforms. It manages the waveform generation process and updates the TES bias values accordingly.

The available waveform types are:
- Sine wave
- Square wave
- Nothing (no waveform)
"""

import pyrogue as pr
import warm_tdm_api
import numpy as np
import time
from functools import partial

def wfsin(t, f, low, high):
    """
    Generate a sine wave waveform.

    Args:
        t (float): Time value.
        f (float): Frequency of the sine wave.
        low (float): Lower limit of the waveform.
        high (float): Upper limit of the waveform.

    Returns:
        float: The value of the sine wave waveform at time `t`.
    """
    return ((high - low) / 2.) * np.sin(2. * np.pi * f * t) + (high + low) / 2.

def wfstep(t, f, low, high):
    """
    Generate a square wave waveform.

    Args:
        t (float): Time value.
        f (float): Frequency of the square wave.
        low (float): Lower limit of the waveform.
        high (float): Upper limit of the waveform.

    Returns:
        float: The value of the square wave waveform at time `t`.
    """
    return (high - low) * (np.floor(t * 2 * f) % 2 >= 1).astype(float) + low

def wfconst(t, const):
    """
    Generate a constant waveform.

    Args:
        t (float): Time value (not used).
        const (float): The constant value to return.

    Returns:
        float: The constant value.
    """
    return const

class TesBiasWaveformProcess(pr.Process):
    """
    TES Bias Waveform Generator Process

    This class manages the generation of various waveforms for the TES bias lines.
    """

    def __init__(self, **kwargs):
        """
        Initialize the TES Bias Waveform Generator Process.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        pr.Process.__init__(self, function=self._tesBiasWaveformWrap, **kwargs)

        self.add(pr.LocalVariable(name='SoftwareClock',
                                  value=1000.,
                                  units='Hz',
                                  mode='RW',
                                  description='Software update rate.'))

        for i in range(8):  # SHOULD REMOVE HARDCODE
            self.add(warm_tdm_api.tesBiasWaveformGenerator(
                name=f'tesBiasWaveformGenerator[{i}]'))

    def _tesBiasWaveformWrap(self):
        """
        Wrap the TES bias waveform generation process.
        """
        tesBiasWaveform(group=self.parent, process=self)

def tesBiasWaveform(*, group, process=None):
    """
    Generate TES bias waveforms and update the TES bias values.

    Args:
        group (pr.Device): The parent device group.
        process (TesBiasWaveformProcess, optional): The TES bias waveform process instance.
    """
    print("TesBiasWaveformProcess Running.")

    # Remember initial biases
    orig_tes_bias = group.TesBias.get()

    # Prepare waveforms
    wfs = []

    # Assumes all generators support same modes
    enum0 = process.tesBiasWaveformGenerator[0].Mode.enum
    modes = []
    for ii in range(8):  # SHOULD REMOVE HARDCODE
        mode = enum0.get(process.tesBiasWaveformGenerator[ii].Mode.get())
        modes.append(mode)
        if mode == 'None':
            const = orig_tes_bias[ii]
            wfs.append(partial(wfconst, const=const))
        else:
            f_hz = process.tesBiasWaveformGenerator[ii].Frequency.get()
            low_ua = process.tesBiasWaveformGenerator[ii].TESBiasLow.get()
            high_ua = process.tesBiasWaveformGenerator[ii].TESBiasHigh.get()
            if mode == 'Sine':
                wfs.append(partial(wfsin, f=f_hz, low=low_ua, high=high_ua))
            if mode == 'Square':
                wfs.append(partial(wfstep, f=f_hz, low=low_ua, high=high_ua))

    # If none of the generators are configured, print error and stop
    if all(mode == 'None' for mode in modes):
        print(f"All generators configured for 'None', nothing to do. Stopping TesBiasWaveformProcess.")
        return

    # Play waveforms
    new_tes_bias = orig_tes_bias.copy()
    last_tes_bias = orig_tes_bias.copy()
    clk_hz = process.SoftwareClock.get()
    dt = 1. / clk_hz
    t0 = time.time()
    counter = 0
    while True:
        step_t = counter * dt
        t = time.time()
        # No rest for the wicked
        while t - t0 < step_t:
            time.sleep(0.000010) # 10 us delay to reduce cpu usage 
            t = time.time()

        new_tes_bias = np.array([wf(t - t0) for wf in wfs])
        if not np.allclose(new_tes_bias, last_tes_bias):
            group.TesBias.set(new_tes_bias)
            last_tes_bias = new_tes_bias.copy()

        # Check for stopped process
        if process is not None and process._runEn == False:
            print(f'TesBiasWaveformProcess stopped, returning TES biases to original values')
            group.TesBias.set(orig_tes_bias)
            break

        counter += 1

class tesBiasWaveformGenerator(pr.Device):
    """
    TES Bias Waveform Generator

    This class provides a way to configure the waveform generation for a single TES bias line.
    """

    def __init__(self, **kwargs):
        """
        Initialize the TES Bias Waveform Generator.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)
        self.add(pr.LocalVariable(
            name='Mode',
            value='None',
            mode='RW',
            enum={
                0: 'None',
                1: 'Square',
                2: 'Sine'}))

        self.add(pr.LocalVariable(name='Frequency',
                                  value=1.0,
                                  units='Hz',
                                  mode='RW',
                                  description='Frequency of waveform generated on TES bias line.'))

        self.add(pr.LocalVariable(name='TESBiasLow',
                                  value=0,
                                  units='uA',
                                  mode='RW',
                                  description='Low-level value of waveform generated on TES bias line.'))

        self.add(pr.LocalVariable(name='TESBiasHigh',
                                  value=1,
                                  units='uA',
                                  mode='RW',
                                  description='High-level value of waveform generated on TES bias line.'))
