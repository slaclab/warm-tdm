# This file is part of the WarmTDM software package. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the WarmTDM software package may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.

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

# Bound Stop latency while waiting for the next software update. This cannot
# interrupt an in-flight hardware transaction; its normal timeout still applies.
_STOP_POLL_SEC = 0.05

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
    """Constant waveform — the 'None' mode; holds `const`, ignoring `t`."""
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

        self.add(pr.LocalVariable(name='UpdateRate',
                                  value=1000.,
                                  units='Hz',
                                  mode='RW',
                                  description=(
                                      'Requested rate at which the host recomputes and writes the '
                                      'TES bias vector (the waveform sample rate, NOT the waveform '
                                      'frequency). Best-effort and host-limited: the real ceiling is '
                                      'the host->board TesBias.set() round-trip rate, so a value '
                                      'above what the link can sustain just lags and logs a warning. '
                                      'Keep it well above the highest per-line Frequency for a smooth '
                                      'waveform. Bench-measured achievable rate is TBD (see issue #55); '
                                      'start conservative (~10-100 Hz) until characterized.')))

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
    """Play a snapshot of the settings; restore biases on Stop or playback error.

    Validate before writing, and attempt restoration even if a waveform write
    fails partway through. A restoration failure is reported, never a successful
    cleanup. Stop is checked while waiting and immediately before each update.
    """
    process._log.info("TesBiasWaveformProcess Running.")

    # Take an independent copy: a device getter may return its mutable cache.
    orig_tes_bias = np.asarray(group.TesBias.get(), dtype=float).copy()
    num_generators = process._waveformGeneratorCount
    if orig_tes_bias.shape != (num_generators,):
        raise ValueError(
            f"TES bias vector shape {orig_tes_bias.shape} does not match "
            f"the number of waveform generators ({num_generators}).")
    if not np.all(np.isfinite(orig_tes_bias)):
        raise ValueError("Initial TES biases must all be finite before playback.")
    if num_generators == 0:
        process._log.warning("No TES bias lines configured; nothing to play.")
        return

    wfs = []
    valid_modes = {'None', 'Sine', 'Square'}
    modes = []
    for ii in range(num_generators):
        gen = process.TesBiasWaveformGenerator[ii]
        mode_value = gen.Mode.get()
        mode = gen.Mode.enum.get(mode_value)
        if mode is None or mode not in valid_modes:
            raise ValueError(
                f"Unsupported TES bias waveform mode for generator {ii}: "
                f"raw value={mode_value!r}, resolved mode={mode!r}. "
                f"Expected one of {sorted(valid_modes)}.")

        modes.append(mode)
        if mode == 'None':
            const = orig_tes_bias[ii]
            wfs.append(partial(wfconst, const=const))
        else:
            f_hz = float(gen.Frequency.get())
            low_ua = float(gen.TESBiasLow.get())
            high_ua = float(gen.TESBiasHigh.get())
            if not np.all(np.isfinite([f_hz, low_ua, high_ua])) or f_hz < 0:
                raise ValueError(
                    f"Generator {ii}: frequency must be finite and nonnegative; "
                    "TES bias levels must be finite.")
            waveform = wfsin if mode == 'Sine' else wfsquare
            wfs.append(partial(waveform, f=f_hz, low=low_ua, high=high_ua))

    if all(mode == 'None' for mode in modes):
        process._log.warning("All generators configured for 'None', nothing to do. Stopping TesBiasWaveformProcess.")
        return

    clk_hz = float(process.UpdateRate.get())
    if not np.isfinite(clk_hz) or clk_hz <= 0:
        raise ValueError(
            f"UpdateRate must be finite and > 0 Hz (got {clk_hz}).")
    dt = 1. / clk_hz
    if not np.isfinite(dt):
        raise ValueError("UpdateRate is too small for a finite update interval.")

    last_tes_bias = orig_tes_bias.copy()
    t0 = time.monotonic()
    counter = 0
    lag_warned = False
    write_attempted = False
    playback_failed = False
    try:
        while process._runEn:
            deadline = t0 + counter * dt
            remaining = deadline - time.monotonic()
            while process._runEn and remaining > 0:
                time.sleep(min(remaining, _STOP_POLL_SEC))
                remaining = deadline - time.monotonic()
            if not process._runEn:
                break

            elapsed = time.monotonic() - t0
            new_tes_bias = np.array([wf(elapsed) for wf in wfs])
            if not np.all(np.isfinite(new_tes_bias)):
                raise ValueError("Waveform generated a non-finite TES bias.")
            if not process._runEn:
                break
            if not np.allclose(new_tes_bias, last_tes_bias):
                # A set can fail after writing only some of the channels.
                write_attempted = True
                group.TesBias.set(new_tes_bias)
                last_tes_bias = new_tes_bias.copy()

            if not lag_warned and time.monotonic() - deadline > dt:
                process._log.warning(
                    f"UpdateRate ({clk_hz} Hz) exceeds the achievable host "
                    "update rate; waveform timing is lagging. Lower UpdateRate.")
                lag_warned = True
            counter += 1
    except BaseException:
        playback_failed = True
        raise
    finally:
        if write_attempted:
            try:
                group.TesBias.set(orig_tes_bias)
            except Exception:
                process._log.exception(
                    "Failed to restore original TES biases; outputs may remain "
                    "at waveform or partially written values.")
                # Preserve the playback exception when both operations failed.
                # On a normal Stop, surface the restoration failure itself.
                if not playback_failed:
                    raise
            else:
                process._log.info("Original TES biases restored.")

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
                1: 'Square',
                2: 'Sine'}))

        self.add(pr.LocalVariable(name='Frequency',
                                  value=1.0,
                                  units='Hz',
                                  mode='RW',
                                  description='Frequency of waveform generated on TES bias line.'))

        self.add(pr.LocalVariable(name='TESBiasLow',
                                  value=0.0,
                                  units='uA',
                                  mode='RW',
                                  description='Low-level value of waveform generated on TES bias line.'))

        self.add(pr.LocalVariable(name='TESBiasHigh',
                                  value=1.0,
                                  units='uA',
                                  mode='RW',
                                  description='High-level value of waveform generated on TES bias line.'))
