from .client import Client

import os
import time
import re
import yaml
import numpy as np

def print_hardware():
    """
    Print the hardware and firmware versions for the column and row boards.

    This function retrieves the hardware version information (build stamp, device DNA, Git hash, and image name)
    for the column and row boards from the `Client.cbs` and `Client.rbs` dictionaries, respectively, and prints
    the information in a formatted way.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})

    if boards:
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
    else:
        print("No column or row boards found.")

def disable_leds():
    """Disable the LEDs on all column and row boards.

    This function iterates through the column boards (Client.cbs) and row boards (Client.rbs)
    dictionaries, and sets the LED enable (LedEn) attribute of the WarmTdmConfig object for
    each board to False, disabling the LEDs.  When disabled, the LEDs are still lit, but no 
    longer blink to indicate status.

    If there are no column boards or row boards available, the function will print a
    corresponding message.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})

    if boards:
        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                board.WarmTdmCore.WarmTdmCommon2.WarmTdmConfig.LedEn.set(False)
                print(f"Disabled LEDs for {board_type} Board {board_index}.")
            except (AttributeError, TypeError) as e:
                print(f"Error disabling LEDs for {board_name}: {e}")
    else:
        print("No column or row boards found.")

def set_cryo_resistance(Rcryo_Ohm):
    """
    Set the cryostat roundtrip resistance for all column and row boards.

    This function iterates through the column boards (Client.cbs) and row boards (Client.rbs)
    dictionaries, and sets the cryostat roundtrip resistance (CableR) for various components
    on each board.

    For column boards, the resistance is set for the following components:
    - SAFbAmp.CableR
    - SQ1BiasAmp.CableR
    - SQ1FbAmp.CableR
    - TesBiasAmp.CableR
    - SAAmp.R_CABLE

    For row boards, the resistance is set for the Amp[rs].CableR, where rs is in the range of 0 to 31.

    If there are no column boards or row boards available, the function will print a
    corresponding message.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})

    if boards:
        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                if board_type == "Column":
                    for ch in range(8):
                        getattr(board.AnalogFrontEnd, f'Channel[{ch}]').SAFbAmp.CableR.set(Rcryo_Ohm)
                        getattr(board.AnalogFrontEnd, f'Channel[{ch}]').SQ1BiasAmp.CableR.set(Rcryo_Ohm)
                        getattr(board.AnalogFrontEnd, f'Channel[{ch}]').SQ1FbAmp.CableR.set(Rcryo_Ohm)
                        getattr(board.AnalogFrontEnd, f'Channel[{ch}]').TesBiasAmp.CableR.set(Rcryo_Ohm)
                        getattr(board.AnalogFrontEnd, f'Channel[{ch}]').SAAmp.R_CABLE.set(Rcryo_Ohm)
                    print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Column Board {board_index}.")
                elif board_type == "Row":
                    for rs in range(32):
                        getattr(board.AnalogFrontEnd, f'Amp[{rs}]').CableR.set(Rcryo_Ohm)
                    print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Row Board {board_index}.")
            except (AttributeError, TypeError) as e:
                print(f"Error setting cryostat resistance for {board_name}: {e}")
    else:
        print("No column or row boards found.")

def set_ps_synch(sync_mode):
    """
    Set the power supply synchronization mode for all column and row boards.

    This function iterates through the column boards (Client.cbs) and row boards (Client.rbs)
    dictionaries, and sets the power supply synchronization registers (PwrSyncA, PwrSyncB,
    PwrSyncC, and PwrSyncEn) based on the provided `sync_mode`.

    Parameters:
    sync_mode (int): 0 to unsynchronize the power supplies, 1 to synchronize the power supplies.

    If there are no column boards or row boards available, the function will print a
    corresponding message.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})

    if boards:
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
    else:
        print("No column or row boards found.")

def check_ps_synch():
    """
    Check the power supply synchronization state for all column and row boards.

    This function iterates through the column boards (Client.cbs) and row boards (Client.rbs)
    dictionaries, and checks the power supply synchronization registers (PwrSyncA, PwrSyncB,
    PwrSyncC, and PwrSyncEn) to determine the overall synchronization state.
    """
    boards = {}
    if Client.cbs:
        boards.update({f"Column {i}": board for i, board in Client.cbs.items()})
    if Client.rbs:
        boards.update({f"Row {i}": board for i, board in Client.rbs.items()})

    sync_state = set()
    for board_name, board in sorted(boards.items()):
        try:
            board_type, board_index = board_name.split(" ")
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
    Extract the column and row values from a channel string.

    Accepted formats are 'c<column>r<row>' and 'r<row>c<column>'.

    Args:
        value (str): Channel identifier string.

    Returns:
        tuple: A `(column, row)` tuple of integers.

    Raises:
        ValueError: If `value` is not in one of the supported formats.
    """
    match = re.fullmatch(r"(?:c(?P<col>\d+)r(?P<row>\d+)|r(?P<row_alt>\d+)c(?P<col_alt>\d+))", value)
    if not match:
        raise ValueError(
            f"Invalid channel format: {value!r}. Expected 'c<column>r<row>' or 'r<row>c<column>'."
        )

    col = match.group("col")
    row = match.group("row")
    if col is None or row is None:
        col = match.group("col_alt")
        row = match.group("row_alt")

    return (int(col), int(row))
def make_dead_masks(channels, ncol=8, nrow=256):
    """
    Generates a dictionary of dead masks, where the keys are the column IDs
    and the values are the corresponding dead mask for that column.
    The dead list row order is not the readout row order; e.g. row
    zero is always chip select 0, row select 0, even if that physical
    channel is not in the readout row order.

    Args:
        channels (list): A list of channels to disable, where each
                         is a string in either 'r<row>c<column>' or
                         'c<column>r<row>' format.

    Returns:
        dict: A dictionary of dead masks, where the keys are the column IDs
              and the values are the corresponding channel masks.
    """
    dead_masks = {}

    # Make masks for all column IDs (0-7)
    for col in range(ncol):
        dead_masks[col] = (1 << nrow) - 1

    # Update the masks for the specified columns
    for channel in channels:
        col, row = get_row_col(channel)
        # Clear the bit corresponding to the specified row
        dead_masks[col] &= ~(1 << row)
    return dead_masks

def write_dead_masks(dead_masks, mask_filename="dead_masks.cfg"):
    """
    Writes the dead channel masks to a configuration file.

    This function takes a dictionary of dead channel masks, where the
    keys are the column IDs and the values are the corresponding dead
    channel masks. It then writes these masks to a configuration file
    in a human-readable format, with each column's mask split into
    groups of 10 bits (for easier readability). The bits are written
    to file for each column starting with the LSB in the mask from left
    to right, in ascending column order.

    Args:
        dead_masks (dict): A dictionary of dead channel masks, where
            the keys are the column IDs and the values are the
            corresponding channel masks.
        mask_filename (str, optional): The name of the configuration
            file to write the dead masks to. Defaults to
            "dead_masks.cfg".

    Returns:
        None
    """
    # Write the column masks to a file
    with open(mask_filename, "w") as f:
        for col, mask in dead_masks.items():
            # Convert the mask to a binary string, with the least significant bit (LSB) first
            binary_mask = f"{mask:0{len(bin(mask)[2:])}b}"[::-1]

            # Split the binary mask into groups of 10 bits for easier readability
            mask_groups = [binary_mask[i:i+10] for i in range(0, len(binary_mask), 10)]

            # Write the formatted mask to the configuration file
            f.write(f"{'   '.join(mask_groups)}\n")

    # Tell user where the dead mask got written to
    print(f"Current dead mask written to {mask_filename}")

def read_dead_masks(mask_filename="dead_masks.cfg"):
    """
    Reads the dead channel masks from a configuration file.

    This function reads the dead channel masks from a configuration file, where each
    line represents the mask for a single column. The mask is expected to be in a
    human-readable format, with each column's mask split into groups of 10 bits.

    Args:
        mask_filename (str, optional): The name of the configuration file to read the
            dead masks from. Defaults to "dead_masks.cfg".

    Returns:
        dict: A dictionary of dead channel masks, where the keys are the column IDs
            and the values are the corresponding channel masks.
    """
    dead_masks = {}

    try:
        with open(mask_filename, "r") as f:
            for col, line in enumerate(f):
                # Get this column's mask, with LSB last.
                binary_mask = re.sub(r"\s+", "", line)[::-1]
                dead_masks[col] = int(binary_mask, 2)

    except FileNotFoundError:
        print(f"Error: {mask_filename} not found.")
        return {}

    return dead_masks

def all_off():
    """
    Turn all signals off and stop multiplexing.  Clean slate.
    """

    #### IN PROGRESS ; NEED TO FIX A FIRMWARE BUG WHICH PREVENTS ZERO'ING
    #### BIASES AFTER DROPPING OUT OF MULTIPLEXING

    # Zero non-multiplexed outputs.

    # Column board signals
    try:
        for r in ['Sq1FbForceCurrent',
                  'Sq1BiasForceCurrent',
                  'SaFbForceCurrent',
                  'SaBiasCurrent',
                  'SaOffset',
                  'TesBias']:
            getattr(Client.client.root.Group,r).set(
                np.zeros_like(getattr(Client.client.root.Group,r).get()))
    except (AttributeError, TypeError) as e:
        print(f"Error zeroing {r} : {e}")

    # If running, end the run.  This should drop us out of 
    # multiplexing, to zeros for every multiplexed output.
    # Assumes ColumnBoard[0] is in charge.
    cb0=Client.cbs[0]
    # If running, end the run.
    if cb0.WarmTdmCore.Timing.TimingTx.Running.get():
        cb0.WarmTdmCore.Timing.TimingTx.EndRun()
    # Switch to manual timing mode    
    cb0.WarmTdmCore.Timing.TimingTx.Mode.set(0)

    # Zero multiplexed outputs

    # Zero row DACs
    #for i, rdd in Client.rdds.items():
    #    rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
    #    rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))

def save_config():
    """
    Save the current configuration of the system to a YAML file.

    This function retrieves the root node of the system, reads all the variables,
    and then saves the current configuration to a YAML file. The file is named
    'config_<timestamp>.yml' and is saved in the current session directory.

    Note:
        This function is targeted towards saving a configuration for later recall.
        You can also use a save_state file for configuration, as the system will
        ignore the read-only (RO) variables.

    Returns:
        str: The full path to the saved file.
    """
    r = Client.client.root

    # Save the configuration
    ctime = int(time.time())
    filename = os.path.join(Client.sessiondir, f'config_{ctime}.yml')
    r.SaveConfig(filename)
    print(f'Saved config to {filename}')
    return filename

def save_state():
    """
    Save the current state of the system to a YAML file.

    This function retrieves the root node of the Rogue system and saves the current
    state of all variables to a YAML file. The file is named 'state_<timestamp>.yml'
    and is saved in the current session directory.

    Note:
        This function saves the complete state of the Rogue system, including all
        read-only (RO) variables. This operation can be slower than saving the
        configuration using the `save_config()` function.

    Returns:
        str: The full path to the saved state file.
    """
    root = Client.client.root

    # Save the state
    ctime = int(time.time())
    state_filename = os.path.join(Client.sessiondir, f'state_{ctime}.yml')
    root.SaveState(state_filename)
    print(f'Saved state to {state_filename}')
    return state_filename

def load_config(filename):
    """
    Load the configuration from a YAML file.

    This function retrieves the root node of the Rogue system and loads the
    configuration from the specified YAML file.

    Args:
        filename (str): The full path to the YAML file containing the configuration.

    Raises:
        FileNotFoundError: If the specified file does not exist.

    Returns:
        None
    """
    root = Client.client.root

    # Check if the file exists before attempting to load the configuration
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Configuration file '{filename}' not found.")

    root.LoadConfig(filename)
    print(f"Loaded configuration from {filename}")

def setup_mux(num_pts=2048, sample_end_offset=100, sample_num=250, strobe=False, enable_pid=True, enable_pid_debug=False):
    """
    Configure the hardware for multiplexed readout and lock the PID loops.

    Sets up timing parameters on the column board, configures the row DAC driver
    for timing mode, and enables PID loops for all enabled columns.

    Args:
        num_pts (int, optional): Number of points per row period cycle. 
            125000 corresponds to 1 kHz. Default is 2048.
        sample_end_offset (int, optional): Buffer (in points) between the last 
            averaged sample and the end of the row period. Default is 100.
        sample_num (int, optional): Number of points to average per sample window.
            Default is 250.
        strobe (bool, optional): If False, sets hardware timing mode (free streaming 
            MUX). If True, sets software mode for manual stepping. Default is False.
        enable_pid (bool, optional): If True, enables SQ1 pid servo for enabled
            readout columns.  Default is True.
        enable_pid_debug (bool, optional): If True, enables streaming a bunch of SQ1
            pid servo debug information.  It will save a lot of extra information so
            doing this at high rates is discouraged and may break things.  
            Default is False.

    Returns:
        None
    """
    # Check that column boards exist
    if not Client.cbs:
        print("Error: No column boards detected. Cannot setup multiplexing.")
        return

    # Check that row boards exist
    if not Client.rbs:
        print("Error: No row boards detected. Cannot setup multiplexing.")
        return

    # Warn if multiple column boards detected
    if len(Client.cbs) > 1:
        print(f"Warning: Multiple column boards detected {list(Client.cbs.keys())}. "
              f"Assuming ColumnBoard[0] is the controller board.")

    # Warn if multiple row boards detected
    if len(Client.rbs) > 1:
        print(f"Warning: Multiple row boards detected {list(Client.rbs.keys())}. "
              f"Applying commands to all row boards.")

    cb = Client.cbs[0]

    # Set timing mode: 1 = hardware MUX mode, 0 = manual software mode
    cb.WarmTdmCore.Timing.TimingTx.Mode.set(0 if strobe else 1)

    # Configure row period and sample window timing
    num_pts = int(num_pts)
    cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.set(num_pts)
    cb.WarmTdmCore.Timing.TimingTx.SampleStartTime.set(num_pts - sample_end_offset - sample_num)
    cb.WarmTdmCore.Timing.TimingTx.SampleEndTime.set(num_pts - sample_end_offset)

    # Set all row boards to timing mode for row switching during MUX
    for rb_idx, rdd in Client.rdds.items():
        rdd.Mode.set(0)
        if len(Client.rdds) > 1:
            print(f"Set RowBoard[{rb_idx}] to timing mode.")

    ## WILL NEED TO EXPAND WHEN START WORKING WITH MORE THAN ONE COLUMN BOARD
    # Enable PID loops for all enabled columns
    col_list = Client.client.root.Group.ColTuneEnable.get()
    for col, enabled in enumerate(col_list):
        if enabled:
            print(f"Enabling PID for column {col}")
            cb.DataPath.AdcDsp[col].ClearPids()
            cb.DataPath.AdcDsp[col].PidEnable.set(enable_pid)
            cb.DataPath.AdcDsp[col].PidDebugEnable.set(enable_pid_debug)
