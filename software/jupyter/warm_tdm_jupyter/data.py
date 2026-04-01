from .client import Client

import os
import time

# Need to add outputdir=None feature
def take_raw(col, synch=False, fadc=125e6, decimation=0, check_delay_sec=0.1):
    """
    Capture raw waveform data from a single column of the detector.

    Args:
        col (int): The column number to capture data from.
        synch (bool, optional): If True, trigger a synchronized waveform capture. Otherwise, trigger an asynchronous capture.
        fadc (float, optional): The FADC sampling rate in Hz. Default is 125e6 (125 MHz).
        decimation (int, optional): The decimation factor to apply to the waveform data. Default is 0 (no decimation).
        check_delay_sec (float, optional): The time in seconds to wait between checks for the saved waveform file. Default is 0.1 (100 ms).

    Returns:
        str: The full path to the saved waveform file.
    """
    # Get the last saved raw dataset filename
    last_raw0 = Client.hwg.WaveformCaptureReceiver.LastSavedFileName.get()
    #print(f'last_raw0 = {last_raw0}')

    # Determine the column board to use
    cb = Client.cbs[int(col / 8)]

    # Add this featuer
    ## Set the output directory if not provided
    #if outputdir is None:
    #    outputdir = Client.sessiondir

    # Enable waveform capture
    Client.hwg.WaveformCaptureReceiver.SaveData.set(True)

    # Configure the waveform capture settings
    cb.DataPath.WaveformCapture.AllChannels.set(False)
    cb.DataPath.WaveformCapture.SelectedChannel.set(col)
    cb.DataPath.WaveformCapture.Decimation.set(decimation)
    Client.hwg.WaveformCaptureReceiver.PlotColumn.set(col)
    Client.hwg.WaveformCaptureReceiver.PlotWaveform.set(True)

    # Trigger the waveform capture
    if synch:
        cb.WarmTdmCore.Timing.TimingTx.WaveformCapture()
    else:
        cb.DataPath.WaveformCapture.CaptureWaveform()

    # Wait for the waveform to be saved to disk
    last_raw = None
    while True:
        if last_raw is not None:
            #print(f'last_raw = {last_raw}')
            #print(f'os.path.getsize(last_raw) = {os.path.getsize(last_raw)}')
            if last_raw != last_raw0 and os.path.getsize(last_raw) > 0:
                time.sleep(1) # wait 1sec or will never converge because waveforms are timestamped only to the second
                break
        time.sleep(check_delay_sec)
        last_raw = Client.hwg.WaveformCaptureReceiver.LastSavedFileName.get()

    # Disable waveform capture
    Client.hwg.WaveformCaptureReceiver.SaveData.set(False)

    # Return the path to the saved waveform file
    return last_raw

def multi_raw(col, nraw, synch=False, decimation=0):
    """
    Capture fast waveforms for multiple columns in a column board.

    This function captures fast waveforms for the specified number of columns on the column
    board (cb). It creates a new directory named "raw_CTIME", where CTIME is the integer
    current time, and saves the waveform files to that directory. Waveforms are indexed
    in that directory in a text file named "raw_CTIME.txt".

    Parameters:
    col (int): The column to take fast waveforms on.
    nraw (int): Number of raw waveforms to take on this column. Must be nonzero.
    synch (bool, optional): Whether to trigger synchronized captures. Default is False.
    decimation (int, optional): The decimation factor. Default is 0.

    Returns:
    str: The full path to the index file containing the saved waveform file paths.
    """
    ctime = int(time.time())
    save_dir = os.path.join(Client.sessiondir, f'raw_{ctime}')
    os.makedirs(save_dir, exist_ok=True)

    wfs = []
    for ii in range(nraw):
        wfs.append(take_raw(col=col, synch=synch))

    idxfn = f'raw_{ctime}.txt'
    idxfp = os.path.join(save_dir, idxfn)
    with open(idxfp, 'w') as f:
        for wf in wfs:
            f.write(f"{wf}\n")

    print(f"{nraw} waveforms indexed to {idxfp} for column {col}.")
    return idxfp