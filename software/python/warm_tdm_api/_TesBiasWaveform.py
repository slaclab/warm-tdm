"""
TES Bias Waveform Generator

This module provides a TES bias waveform generator to create various waveforms for testing and characterization purposes.

The `TesBiasWaveformProcess` class is the main entry point for generating waveforms. It manages the waveform generation process and updates the TES bias values accordingly.

The available waveform types are:
- Sine wave
- Square wave
- None (hold the original bias)
"""

import pyrogue as pr
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

def wfsquare(t, f, low, high):
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
    One `TesBiasWaveformGenerator` sub-device is created per TES bias entry
    (``config.numColumns`` == ``ColumnBoards * 8``) at construction time.
    """

    def __init__(self, *, config, **kwargs):
        """
        Initialize the TES Bias Waveform Generator Process.

        Args:
            config: Group configuration (provides ``numColumns``, i.e. the TES
                bias vector length). Used to size the generator list once, here
                at construction time.
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        pr.Process.__init__(self, function=self._tesBiasWaveformWrap, **kwargs)

        self._config = config

        self.add(pr.LocalVariable(name='SoftwareClock',
                                  value=1000.,
                                  units='Hz',
                                  mode='RW',
                                  description='Software update rate.'))

        # One generator per TES bias entry. The TES bias vector has length
        # ColumnBoards * 8 == config.numColumns, so size the generator list from
        # config at construction time (the parent isn't attached yet in __init__,
        # and mutating the device tree at run time would desync connected clients).
        self._waveformGeneratorCount = config.numColumns
        for i in range(self._waveformGeneratorCount):
            self.add(TesBiasWaveformGenerator(
                name=f'TesBiasWaveformGenerator[{i}]'))

    def _tesBiasWaveformWrap(self):
        """
        Wrap the TES bias waveform generation process.
        """
        tesBiasWaveform(group=self.parent, process=self)

def tesBiasWaveform(*, group, process):
    """
    Generate TES bias waveforms and update the TES bias values.

    Args:
        group (pr.Device): The parent device group.
        process (TesBiasWaveformProcess): The TES bias waveform process instance.
    """
    process._log.info("TesBiasWaveformProcess Running.")

    # Remember initial biases
    orig_tes_bias = group.TesBias.get()

    # Prepare waveforms
    wfs = []

    # One generator per TES bias entry, sized from config at construction.
    num_generators = process._waveformGeneratorCount
    if len(orig_tes_bias) != num_generators:
        raise ValueError(
            f"TES bias vector length ({len(orig_tes_bias)}) does not match "
            f"the number of waveform generators ({num_generators}).")

    enum0 = process.TesBiasWaveformGenerator[0].Mode.enum
    valid_modes = {'None', 'Sine', 'Square'}
    modes = []
    for ii in range(num_generators):
        mode_value = process.TesBiasWaveformGenerator[ii].Mode.get()
        mode = enum0.get(mode_value)
        if mode is None or mode not in valid_modes:
            raise ValueError(
                f"Unsupported TES bias waveform mode for generator {ii}: "
                f"raw value={mode_value!r}, resolved mode={mode!r}. "
                f"Expected one of {sorted(valid_modes)}.")

        modes.append(mode)
        if mode == 'None':
            const = orig_tes_bias[ii]
            wfs.append(partial(wfconst, const=const))
        elif mode == 'Sine':
            f_hz = process.TesBiasWaveformGenerator[ii].Frequency.get()
            low_ua = process.TesBiasWaveformGenerator[ii].TESBiasLow.get()
            high_ua = process.TesBiasWaveformGenerator[ii].TESBiasHigh.get()
            wfs.append(partial(wfsin, f=f_hz, low=low_ua, high=high_ua))
        elif mode == 'Square':
            f_hz = process.TesBiasWaveformGenerator[ii].Frequency.get()
            low_ua = process.TesBiasWaveformGenerator[ii].TESBiasLow.get()
            high_ua = process.TesBiasWaveformGenerator[ii].TESBiasHigh.get()
            wfs.append(partial(wfsquare, f=f_hz, low=low_ua, high=high_ua))
        else:
            raise ValueError(
                f"Unhandled TES bias waveform mode for generator {ii}: {mode!r}")

    if len(wfs) != len(orig_tes_bias):
        raise ValueError(
            f"Generated {len(wfs)} waveform functions for "
            f"{len(orig_tes_bias)} TES bias entries.")
    # If none of the generators are configured, print error and stop
    if all(mode == 'None' for mode in modes):
        process._log.warning("All generators configured for 'None', nothing to do. Stopping TesBiasWaveformProcess.")
        return

    # Play waveforms
    new_tes_bias = orig_tes_bias.copy()
    last_tes_bias = orig_tes_bias.copy()
    clk_hz = process.SoftwareClock.get()
    if clk_hz <= 0:
        raise ValueError(
            f"SoftwareClock must be > 0 Hz (got {clk_hz}).")
    dt = 1. / clk_hz
    t0 = time.time()
    counter = 0
    lag_warned = False
    while True:
        step_t = counter * dt
        # Sleep until the next tick rather than busy-polling, so a high
        # SoftwareClock doesn't spin the server CPU (remaining may be <= 0 if
        # we're already behind, in which case we proceed immediately).
        remaining = step_t - (time.time() - t0)
        if remaining > 0:
            time.sleep(remaining)
        t = time.time()

        new_tes_bias = np.array([wf(t - t0) for wf in wfs])
        if not np.allclose(new_tes_bias, last_tes_bias):
            group.TesBias.set(new_tes_bias)
            last_tes_bias = new_tes_bias.copy()

        # Warn (once) if the software can't sustain the requested SoftwareClock:
        # if we've fallen a full sample behind schedule after the set, the
        # host/link latency exceeds the requested update period (see #55).
        if not lag_warned and (time.time() - t0) - step_t > dt:
            process._log.warning(
                f"SoftwareClock ({clk_hz} Hz) exceeds the achievable software "
                f"update rate; waveform timing is lagging. Lower SoftwareClock.")
            lag_warned = True

        # Check for stopped process
        if process._runEn is False:
            process._log.info('TesBiasWaveformProcess stopped, returning TES biases to original values')
            group.TesBias.set(orig_tes_bias)
            break

        counter += 1

class TesBiasWaveformGenerator(pr.Device):
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
            value=0,
            mode='RW',
            enum={
                0: 'None',
                1: 'Sine',
                2: 'Square'}))

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
