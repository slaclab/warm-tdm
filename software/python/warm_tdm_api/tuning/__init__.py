"""Hardware-facing SA, FAS, and SQ1 tuning routines.

The public functions operate on the Group-level PyRogue array variables. Those
variables apply ``ColTuneEnable`` and batch accesses to the underlying boards,
so tuning code passes complete column vectors rather than walking individual
board/channel nodes. Long-running sweeps cooperate with Process Stop/Pause
requests and may publish partial curve data at safe points.

This package replaces the former monolithic ``_Tuning.py``. It is split by
tuning stage over a shared-primitive core:

- ``_common`` : ``saOffset``, ``saFbServo`` and the ``_pause_point`` helper,
  reused across stages.
- ``_sa``     : SA amplifier tune (``saTune`` and its sweeps).
- ``_sq1``    : SQ1 tune (``sq1Tune`` and its sweeps).
- ``_fas``    : FAS tune (``fasTune`` and its sweep).
- ``_ramp``   : SQ1-feedback and TES-bias diagnostic ramps.

The public API is unchanged from ``_Tuning.py``; import these as
``warm_tdm_api.<name>``.
"""

from ._common import saOffset, saFbServo
from ._sa import saFbSweep, saBiasSweep, saTune
from ._sq1 import sq1FbSweep, sq1BiasSweep, sq1Tune
from ._fas import fasSweep, fasTune
from ._ramp import sq1Ramp, sq1RampRow, tesRamp, tesRampRow

__all__ = [
    'saOffset',
    'saFbServo',
    'saFbSweep',
    'saBiasSweep',
    'saTune',
    'sq1FbSweep',
    'sq1BiasSweep',
    'sq1Tune',
    'fasSweep',
    'fasTune',
    'sq1Ramp',
    'sq1RampRow',
    'tesRamp',
    'tesRampRow',
]
