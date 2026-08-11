"""warm_tdm_api.operations — client-side operational layer for Warm TDM.

A cohesive, deliberately runtime-editable layer of procedures for *running* the
system from a client (notebook, script, or production tooling): session/board
management, data acquisition, hardware setup helpers, stream reading, and offline
analysis/plotting. It drives the warm_tdm_api rogue tree remotely; it is distinct
from the pyrogue-tree device modules (`_Group`, `_SaTune`, ...) by design.

Reusable hardware capabilities here (e.g. setup_mux, all_off) are candidates to
graduate into Group as they mature — see docs/plans/wtj-refactor.
"""

# Session / hardware connection
from .client import Client

# Hardware setup + config helpers
from .utils import (
    print_hardware,
    disable_leds,
    set_cryo_resistance,
    set_ps_synch,
    check_ps_synch,
    get_row_col,
    make_dead_masks,
    write_dead_masks,
    read_dead_masks,
    all_off,
    save_config,
    save_state,
    load_config,
    setup_mux,
)

# Data acquisition
from .data import (
    StreamData,
    take_raw,
    multi_raw,
    take_data,
)

# Stream file reading
from .streamreader import StreamReader

# Calibration constant derivation (from a capture's embedded tree config)
from .calibration import (
    derive_fs,
    derive_sq1fb_to_pA,
    resolve_fs,
    resolve_sq1fb_to_pA,
    DEFAULT_FS,
    DEFAULT_SQ1FB_TO_PA,
)

# Offline analysis + plotting
from .analysis import (
    add_channel_legend,
    make_color_cycle,
    expand_channels,
    plot_stream_data,
    analyze_pair,
    simple_noise_model,
    get_mean_raw_asd,
    plot_sq1curves,
)

__all__ = [
    'Client',
    # utils
    'print_hardware',
    'disable_leds',
    'set_cryo_resistance',
    'set_ps_synch',
    'check_ps_synch',
    'get_row_col',
    'make_dead_masks',
    'write_dead_masks',
    'read_dead_masks',
    'all_off',
    'save_config',
    'save_state',
    'load_config',
    'setup_mux',
    # data
    'StreamData',
    'take_raw',
    'multi_raw',
    'take_data',
    # streamreader
    'StreamReader',
    # calibration
    'derive_fs',
    'derive_sq1fb_to_pA',
    'resolve_fs',
    'resolve_sq1fb_to_pA',
    'DEFAULT_FS',
    'DEFAULT_SQ1FB_TO_PA',
    # analysis
    'add_channel_legend',
    'make_color_cycle',
    'expand_channels',
    'plot_stream_data',
    'analyze_pair',
    'simple_noise_model',
    'get_mean_raw_asd',
    'plot_sq1curves',
]
