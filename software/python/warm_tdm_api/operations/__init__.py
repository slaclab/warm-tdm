"""warm_tdm_api.operations — client-side operational layer for Warm TDM.

A cohesive, deliberately runtime-editable layer of procedures for *running* the
system from a client (notebook, script, or production tooling): session/board
management, data acquisition, hardware setup helpers, stream reading, and offline
analysis/plotting. It drives the warm_tdm_api rogue tree remotely; it is distinct
from the pyrogue-tree device modules (`_Group`, `_SaTune`, ...) by design.

Hardware-coupled operations live on the `Session` object (an explicit, injectable
handle around a connected client). For notebook convenience a process-wide default
Session can be established with `connect()`/`use()`, after which the free-function
shims (`ops.take_raw(0)`, `ops.setup_mux()`, ...) delegate to it. Scripts and tests
should prefer calling methods on an explicit Session.
"""

# Hardware handle + session management
from .session import (
    Session,
    OutputDir,
    connect,
    use,
    set_default_session,
    get_default_session,
    # free-function shims that delegate to the default Session
    print_hardware,
    disable_leds,
    set_cryo_resistance,
    set_ps_synch,
    check_ps_synch,
    all_off,
    save_config,
    save_state,
    load_config,
    setup_mux,
    take_raw,
    multi_raw,
    take_data,
    new_session,
)

# Pure format / bitmask / file helpers (no hardware)
from .formats import (
    get_row_col,
    make_dead_masks,
    write_dead_masks,
    read_dead_masks,
)

# Stream data container + file reading
from .data import StreamData
from .streamreader import StreamReader

# Unit-conversion factor derivation (from a capture's embedded tree config)
from .unit_conversions import (
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
    channel_timeseries,
    compute_asd,
    plot_stream_data,
    analyze_pair,
    simple_noise_model,
    get_mean_raw_asd,
    plot_sq1curves,
)

__all__ = [
    # session
    'Session',
    'OutputDir',
    'connect',
    'use',
    'set_default_session',
    'get_default_session',
    'new_session',
    # session shims (hardware setup)
    'print_hardware',
    'disable_leds',
    'set_cryo_resistance',
    'set_ps_synch',
    'check_ps_synch',
    'all_off',
    'save_config',
    'save_state',
    'load_config',
    'setup_mux',
    # session shims (acquisition)
    'take_raw',
    'multi_raw',
    'take_data',
    # formats
    'get_row_col',
    'make_dead_masks',
    'write_dead_masks',
    'read_dead_masks',
    # data / streamreader
    'StreamData',
    'StreamReader',
    # unit conversions
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
    'channel_timeseries',
    'compute_asd',
    'plot_stream_data',
    'analyze_pair',
    'simple_noise_model',
    'get_mean_raw_asd',
    'plot_sq1curves',
]
