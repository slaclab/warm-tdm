from .client import Client

import os
import time
import re
import numpy as np


def _get_boards():
    """
    Return a dict of all connected column and row boards, keyed by 'Column N' / 'Row N'.

    Returns:
        dict: Combined mapping of board name to board object. Empty if no boards connected.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})
    return boards


def print_hardware():
    """
    Print firmware and hardware version info for all connected column and row boards.

    Prints BuildStamp, DeviceDNA, Git hash, and image name for each board.
    """
    boards = _get_boards()

    if not boards:
        print("No column or row boards found.")
        return

    print("+" * 80)
    print("Hardware Information")
    print("+" * 80)
    for board_name, board in sorted(boards.items()):
        try:
            board_type, board_index = board_name.split(" ")
            print(f"{board_type} Board {board_index}:")
            print(f"  BuildStamp       : {board.WarmTdmCore.WarmTdmCommon2.AxiVersion.BuildStamp.get()}")
            print(f"  DeviceDna        : {hex(board.WarmTdmCore.WarmTdmCommon2.AxiVersion.DeviceDna.get())}")
            print(f"  Git hash         : {hex(board.WarmTdmCore.WarmTdmCommon2.AxiVersion.GitHash.get())}")
            print(f"  Image Name       : {board.WarmTdmCore.WarmTdmCommon2.AxiVersion.ImageName.get()}")
            print("---")
        except (AttributeError, TypeError) as e:
            print(f"Error retrieving information for {board_name}: {e}")
    print("+" * 80)


def disable_leds():
    """
    Disable status-blinking LEDs on all column and row boards.

    Sets LedEn=False on every board's WarmTdmConfig. The LEDs remain physically
    lit but stop blinking to indicate status.
    """
    boards = _get_boards()

    if not boards:
        print("No column or row boards found.")
        return

    for board_name, board in sorted(boards.items()):
        try:
            board_type, board_index = board_name.split(" ")
            board.WarmTdmCore.WarmTdmCommon2.WarmTdmConfig.LedEn.set(False)
            print(f"Disabled LEDs for {board_type} Board {board_index}.")
        except (AttributeError, TypeError) as e:
            print(f"Error disabling LEDs for {board_name}: {e}")


def set_cryo_resistance(Rcryo_Ohm):
    """
    Set the cryostat roundtrip cable resistance on all column and row boards.

    This value is used by the analog front-end amplifiers to compensate for
    resistive losses in the cables running to the cryostat.

    Column boards: sets CableR on SAFbAmp, SQ1BiasAmp, SQ1FbAmp, TesBiasAmp,
                   and R_CABLE on SAAmp, for all 8 channels.
    Row boards:    sets CableR on Amp[0..31].

    Args:
        Rcryo_Ohm (float): Roundtrip cable resistance in Ohms.
    """
    boards = _get_boards()

    if not boards:
        print("No column or row boards found.")
        return

    for board_name, board in sorted(boards.items()):
        try:
            board_type, board_index = board_name.split(" ")
            if board_type == "Column":
                for ch in range(8):
                    # Use a local reference to avoid repeating the long attribute path
                    afe_ch = getattr(board.AnalogFrontEnd, f'Channel[{ch}]')
                    afe_ch.SAFbAmp.CableR.set(Rcryo_Ohm)
                    afe_ch.SQ1BiasAmp.CableR.set(Rcryo_Ohm)
                    afe_ch.SQ1FbAmp.CableR.set(Rcryo_Ohm)
                    afe_ch.TesBiasAmp.CableR.set(Rcryo_Ohm)
                    afe_ch.SAAmp.R_CABLE.set(Rcryo_Ohm)
                print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Column Board {board_index}.")
            elif board_type == "Row":
                for rs in range(32):
                    getattr(board.AnalogFrontEnd, f'Amp[{rs}]').CableR.set(Rcryo_Ohm)
                print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Row Board {board_index}.")
        except (AttributeError, TypeError) as e:
            print(f"Error setting cryostat resistance for {board_name}: {e}")


def set_ps_synch(sync_mode):
    """
    Set the power supply synchronization mode on all column and row boards.

    Synchronized mode locks the switching supplies across boards to a common
    phase to reduce interference in the detector band.

    Synchronized   (sync_mode=1): PwrSyncA/B/C = 2, PwrSyncEn = 1
    Unsynchronized (sync_mode=0): PwrSyncA/B/C = 0, PwrSyncEn = 0

    Args:
        sync_mode (int): 1 to synchronize, 0 to unsynchronize.
    """
    boards = _get_boards()

    if not boards:
        print("No column or row boards found.")
        return

    for board_name, board in sorted(boards.items()):
        try:
            board_type, board_index = board_name.split(" ")
            if sync_mode == 0:
                board.WarmTdmCore.Timing.TimingTx.PwrSyncA.set(0)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncB.set(0)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncC.set(0)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncEn.set(0)
                print(f"Unsynchronized power supplies for {board_type} Board {board_index}.")
            elif sync_mode == 1:
                board.WarmTdmCore.Timing.TimingTx.PwrSyncA.set(2)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncB.set(2)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncC.set(2)
                board.WarmTdmCore.Timing.TimingTx.PwrSyncEn.set(1)
                print(f"Synchronized power supplies for {board_type} Board {board_index}.")
            else:
                print(f"Invalid sync_mode value: {sync_mode}")
        except (AttributeError, TypeError) as e:
            print(f"Error setting power supply synchronization for {board_name}: {e}")


def check_ps_synch():
    """
    Print the power supply synchronization state across all boards.

    Reads PwrSyncA/B/C and PwrSyncEn from each board and reports whether all
    boards are synchronized, all unsynchronized, or in a mixed state.
    """
    boards = _get_boards()

    if not boards:
        print("No column or row boards found.")
        return

    sync_state = set()
    for board_name, board in sorted(boards.items()):
        try:
            # A board is synchronized when PwrSyncA/B/C == 2 and PwrSyncEn == 1
            if (
                board.WarmTdmCore.Timing.TimingTx.PwrSyncA.get() == 2
                and board.WarmTdmCore.Timing.TimingTx.PwrSyncB.get() == 2
                and board.WarmTdmCore.Timing.TimingTx.PwrSyncC.get() == 2
                and board.WarmTdmCore.Timing.TimingTx.PwrSyncEn.get() == 1
            ):
                sync_state.add("Synchronized")
            else:
                sync_state.add("Unsynchronized")
        except (AttributeError, TypeError) as e:
            print(f"Error checking power supply synchronization for {board_name}: {e}")

    if len(sync_state) == 1:
        print(f"Power supplies are {sync_state.pop()}.")
    else:
        print("Power supplies are in a mixed state (some synchronized, some unsynchronized).")


def get_row_col(value):
    """
    Extract column and row indices from a channel string.

    Accepts 'c<col>r<row>' or 'r<row>c<col>' format.

    Args:
        value (str): Channel identifier, e.g. 'c0r5' or 'r5c0'.

    Returns:
        tuple: (col, row) as integers.

    Raises:
        ValueError: If value does not match either accepted format.
    """
    match = re.fullmatch(r"(?:c(?P<col>\d+)r(?P<row>\d+)|r(?P<row_alt>\d+)c(?P<col_alt>\d+))", value)
    if not match:
        raise ValueError(
            f"Invalid channel format: {value!r}. Expected 'c<col>r<row>' or 'r<row>c<col>'."
        )

    col = match.group("col")
    row = match.group("row")
    # Handle r<row>c<col> format
    if col is None or row is None:
        col = match.group("col_alt")
        row = match.group("row_alt")

    return (int(col), int(row))


def make_dead_masks(channels, ncol=8, nrow=256):
    """
    Build a per-column bitmask marking specified channels as dead (disabled).

    Each mask is an nrow-bit integer where 1 = active, 0 = dead. Row order is
    physical (chip select / row select), not readout order.

    Args:
        channels (list): Channel strings to mark dead, e.g. ['c0r5', 'r3c1'].
        ncol (int): Number of columns. Default is 8.
        nrow (int): Number of rows (bits) per mask. Default is 256.

    Returns:
        dict: {col: mask} where mask is an nrow-bit integer.
    """
    # Start with all channels active (all bits set)
    dead_masks = {col: (1 << nrow) - 1 for col in range(ncol)}

    # Clear the bit for each dead channel
    for channel in channels:
        col, row = get_row_col(channel)
        dead_masks[col] &= ~(1 << row)

    return dead_masks


def write_dead_masks(dead_masks, mask_filename="dead_masks.cfg", nrow=256):
    """
    Write dead channel masks to a human-readable configuration file.

    Each line corresponds to one column (ascending order). Bits are written
    LSB-first, left to right, in groups of 10 for readability.

    Args:
        dead_masks (dict): {col: mask} as returned by make_dead_masks().
        mask_filename (str): Output file path. Default is 'dead_masks.cfg'.
        nrow (int): Number of rows (bits) per mask. Default is 256.
    """
    with open(mask_filename, "w") as f:
        for col, mask in dead_masks.items():
            # Convert to fixed-width binary string, LSB first
            binary_mask = f"{mask:0{nrow}b}"[::-1]
            # Split into groups of 10 bits for readability
            mask_groups = [binary_mask[i:i+10] for i in range(0, nrow, 10)]
            f.write(f"{'   '.join(mask_groups)}\n")

    print(f"Current dead mask written to {mask_filename}")


def read_dead_masks(mask_filename="dead_masks.cfg", nrow=256):
    """
    Read dead channel masks from a file written by write_dead_masks().

    Args:
        mask_filename (str): Path to the mask file. Default is 'dead_masks.cfg'.
        nrow (int): Expected number of bits per mask. Must match the value used
            when writing. Default is 256.

    Returns:
        dict: {col: mask} integers, or empty dict if file not found.

    Raises:
        ValueError: If any line has the wrong number of bits.
    """
    dead_masks = {}
    try:
        with open(mask_filename, "r") as f:
            for col, line in enumerate(f):
                # Strip all whitespace (spaces between groups and newline)
                binary_mask = re.sub(r"\s+", "", line)
                if len(binary_mask) != nrow:
                    raise ValueError(
                        f"Row {col} in '{mask_filename}' has {len(binary_mask)} bits, expected {nrow}."
                    )
                # File stores LSB first; reverse before converting to int
                dead_masks[col] = int(binary_mask[::-1], 2)
    except FileNotFoundError:
        print(f"Error: {mask_filename} not found.")
        return {}
    return dead_masks


def all_off():
    """
    Zero all signal outputs and stop multiplexing. Use as a clean-slate reset.

    Zeros all non-multiplexed column board outputs (SQ1/SA/TES bias and feedback),
    ends any active run, and switches ColumnBoard[0] to manual timing mode.

    Note:
        IN PROGRESS: a firmware bug currently prevents zeroing biases after
        dropping out of multiplexing. Row DAC zeroing is also commented out
        pending resolution.
    """
    # Zero non-multiplexed column board outputs
    try:
        for r in ['Sq1FbForceCurrent',
                  'Sq1BiasForceCurrent',
                  'SaFbForceCurrent',
                  'SaBiasCurrent',
                  'SaOffset',
                  'TesBias']:
            getattr(Client.client.root.Group, r).set(
                np.zeros_like(getattr(Client.client.root.Group, r).get()))
    except (AttributeError, TypeError) as e:
        print(f"Error zeroing {r} : {e}")

    # End the run if active — dropping out of MUX should zero multiplexed outputs.
    # Assumes ColumnBoard[0] is the timing controller.
    cb0 = Client.cbs[0]
    if cb0.WarmTdmCore.Timing.TimingTx.Running.get():
        cb0.WarmTdmCore.Timing.TimingTx.EndRun()

    # Switch to manual (non-MUX) timing mode
    cb0.WarmTdmCore.Timing.TimingTx.Mode.set(0)

    # TODO: zero row DACs once firmware bug is resolved
    #for i, rdd in Client.rdds.items():
    #    rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
    #    rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))


def save_config():
    """
    Save the current hardware configuration to a timestamped YAML file.

    Saves only writable (non-RO) variables. Use for configurations intended
    to be recalled with load_config(). For a full snapshot including read-only
    variables, use save_state() instead.

    Returns:
        str: Path to the saved file (e.g. '<sessiondir>/config_<ctime>.yml').
    """
    r = Client.client.root
    ctime = int(time.time())
    filename = os.path.join(Client.sessiondir, f'config_{ctime}.yml')
    r.SaveConfig(filename)
    print(f'Saved config to {filename}')
    return filename


def save_state():
    """
    Save the complete system state (including read-only variables) to a YAML file.

    Slower than save_config() because it captures all variables. Useful for
    debugging or archiving a full hardware snapshot.

    Returns:
        str: Path to the saved file (e.g. '<sessiondir>/state_<ctime>.yml').
    """
    root = Client.client.root
    ctime = int(time.time())
    state_filename = os.path.join(Client.sessiondir, f'state_{ctime}.yml')
    root.SaveState(state_filename)
    print(f'Saved state to {state_filename}')
    return state_filename


def load_config(filename):
    """
    Load a hardware configuration from a YAML file saved by save_config().

    Read-only variables in the file are silently ignored by the Rogue framework.

    Args:
        filename (str): Path to the YAML configuration file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Configuration file '{filename}' not found.")

    Client.client.root.LoadConfig(filename)
    print(f"Loaded configuration from {filename}")


def setup_mux(num_pts=2048, sample_end_offset=100, sample_num=250, strobe=False, enable_pid=True, enable_pid_debug=False):
    """
    Configure hardware for multiplexed (MUX) readout and enable PID servo loops.

    Sets the row period and sample window timing on ColumnBoard[0], puts all row
    DAC drivers into timing mode, and enables the SQ1 PID loops for all columns
    marked active in ColTuneEnable.

    The sample window sits near the end of each row period:
        SampleStartTime = num_pts - sample_end_offset - sample_num
        SampleEndTime   = num_pts - sample_end_offset

    Args:
        num_pts (int): Row period in ADC clock cycles. 125000 ≈ 1 kHz row rate.
            Default is 2048.
        sample_end_offset (int): Guard buffer (in cycles) between the last sample
            and end of the row period. Default is 100.
        sample_num (int): Number of cycles to average per sample window. Default is 250.
        strobe (bool): If False (default), hardware free-running MUX mode (Mode=1).
            If True, software-stepped mode (Mode=0) for manual row control.
        enable_pid (bool): Enable SQ1 PID servo for active columns. Default is True.
        enable_pid_debug (bool): Stream PID debug data. Avoid at fast row rates —
            high data volume may cause issues. Default is False.
    """
    if not Client.cbs:
        print("Error: No column boards detected. Cannot setup multiplexing.")
        return

    if not Client.rbs:
        print("Error: No row boards detected. Cannot setup multiplexing.")
        return

    if len(Client.cbs) > 1:
        print(f"Warning: Multiple column boards detected {list(Client.cbs.keys())}. "
              f"Assuming ColumnBoard[0] is the controller board.")

    if len(Client.rbs) > 1:
        print(f"Warning: Multiple row boards detected {list(Client.rbs.keys())}. "
              f"Applying commands to all row boards.")

    cb = Client.cbs[0]

    # Mode 1 = hardware MUX (free-running), Mode 0 = software-stepped
    cb.WarmTdmCore.Timing.TimingTx.Mode.set(0 if strobe else 1)

    # Set row period and sample window timing
    num_pts = int(num_pts)
    cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.set(num_pts)
    cb.WarmTdmCore.Timing.TimingTx.SampleStartTime.set(num_pts - sample_end_offset - sample_num)
    cb.WarmTdmCore.Timing.TimingTx.SampleEndTime.set(num_pts - sample_end_offset)

    # Put all row DAC drivers in timing mode so they switch rows during MUX
    for rb_idx, rdd in Client.rdds.items():
        rdd.Mode.set(0)
        if len(Client.rdds) > 1:
            print(f"Set RowBoard[{rb_idx}] to timing mode.")

    # TODO: expand to support multiple column boards
    # Enable PID for all columns flagged active in ColTuneEnable
    col_list = Client.client.root.Group.ColTuneEnable.get()
    for col, enabled in enumerate(col_list):
        if enabled:
            print(f"Enabling PID for column {col}")
            cb.DataPath.AdcDsp[col].ClearPids()
            cb.DataPath.AdcDsp[col].PidEnable.set(enable_pid)
            cb.DataPath.AdcDsp[col].PidDebugEnable.set(enable_pid_debug)
