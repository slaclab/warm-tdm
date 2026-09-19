# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Pure unit conversion for the floating-point servo's wrap registers."""
import math
import numbers
import struct


# Centered wrapping leaves one code of headroom at the positive DAC rail.
MAX_WRAP_PERIOD = 16380.0


def float32(value):
    try:
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('Value is outside the float32 range') from exc
    if not math.isfinite(result):
        raise ValueError('Value must be finite in float32')
    return result


def flux_period_registers(current, current_per_lsb, multiplier):
    """Return (physical period, stored wrap period, stored reciprocal).

    Periods are differences in signed controller DAC-code units. Validate the
    entire pair before the caller writes anything. The quotient bound includes
    any 14-bit initial seed and the specified 256-physical-quantum excursion.
    """
    if isinstance(multiplier, bool) or not isinstance(multiplier, numbers.Integral) or multiplier < 1:
        raise ValueError('WrapMultiplier must be a positive integer')
    current = float(current)
    slope = abs(float(current_per_lsb))
    if not math.isfinite(current) or current < 0:
        raise ValueError('FluxQuantum must be a finite nonnegative period')
    if not math.isfinite(slope) or slope == 0:
        raise ValueError('The SQ1 feedback current-per-code slope must be finite and nonzero')
    quantum = current / slope
    try:
        period = float32(quantum * multiplier)
    except OverflowError as exc:
        raise ValueError('WrapMultiplier is too large') from exc
    if current == 0:
        return 0.0, 0.0, 0.0
    if period <= 0 or period > MAX_WRAP_PERIOD:
        raise ValueError(f'Wrap period must be positive and at most {MAX_WRAP_PERIOD:g} DAC codes')
    if 8192.0 / period + 256.0 / multiplier >= (1 << 31) - 1:
        raise ValueError('Wrap period is too small for the signed 32-bit wrap quotient')
    reciprocal = float32(1.0 / period)
    return quantum, period, reciprocal
