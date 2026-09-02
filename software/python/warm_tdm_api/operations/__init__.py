"""warm_tdm_api.operations — client-side operational layer for Warm TDM.

A cohesive, deliberately runtime-editable layer of procedures for *running* the
system from a client (notebook, script, or production tooling): session/board
management, hardware setup helpers, data acquisition, tuning (start-and-block
wrappers over the Group tuning processes), stream reading, and offline
analysis/plotting. It drives the warm_tdm_api rogue tree remotely; it is distinct
from the pyrogue-tree device modules (`_Group`, `_SaTune`, ...) by design.

The operator arc reads end to end: `connect` -> `setup_mux` -> `sa_tune`/
`sq1_tune` -> `take_data` -> `plot_stream_data`, with `status()` for state and
`stop_and_zero()` for a best-effort safe baseline.

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
    status,
    disable_leds,
    set_cryo_resistance,
    set_ps_synch,
    check_ps_synch,
    stop_and_zero,
    save_config,
    save_state,
    load_config,
    setup_mux,
    apply_dead_masks,
    take_raw,
    multi_raw,
    take_data,
    run_process,
    sa_offset,
    sa_tune,
    sq1_tune,
    new_session,
)

# Pure channel helpers: addressing, identifiers, dead masks (no hardware)
from .channels import (
    get_row_col,
    make_dead_masks,
    write_dead_masks,
    read_dead_masks,
)

# Stream data containers + file reading
from .data import StreamData, PidDebugData
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
    plot_pid_debug,
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
    'status',
    'disable_leds',
    'set_cryo_resistance',
    'set_ps_synch',
    'check_ps_synch',
    'stop_and_zero',
    'save_config',
    'save_state',
    'load_config',
    'setup_mux',
    'apply_dead_masks',
    # session shims (acquisition)
    'take_raw',
    'multi_raw',
    'take_data',
    # session shims (tuning)
    'run_process',
    'sa_offset',
    'sa_tune',
    'sq1_tune',
    # channels (addressing, identifiers, dead masks)
    'get_row_col',
    'make_dead_masks',
    'write_dead_masks',
    'read_dead_masks',
    # data / streamreader
    'StreamData',
    'PidDebugData',
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
    'plot_pid_debug',
]
