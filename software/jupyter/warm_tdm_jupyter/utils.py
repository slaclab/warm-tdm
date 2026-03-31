from .client import Client

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