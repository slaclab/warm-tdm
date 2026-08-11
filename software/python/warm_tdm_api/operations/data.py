from .client import Client
from .streamreader import StreamReader

import os
import time
from collections import deque

class StreamData:
    """
    A class that manages the loading and caching of stream data from files.

    This class represents a single stream data file and its associated data. When an
    instance of this class is created, it attempts to load the data from the specified
    file path. If the file is not found, it raises a `FileNotFoundError`. The loaded
    data is stored in the `data` attribute of the instance.

    The class keeps a bounded registry of the most recently created instances
    (the last ``_MAX_INSTANCES``) so long-running sessions don't leak memory as
    files are loaded. Instances are retrievable by position (``-1`` is the most
    recent), by their stable monotonic ``index`` id, or by file name -- as long
    as they are still within the retained window.

    Attributes:
        _instances (deque): Bounded registry of recent `StreamData` instances.
        index (int): Stable monotonic id assigned at creation (NOT a position in
            the registry; survives eviction of older instances). Used for
            identity/repr and get_by_index().
        file_path (str): The full path to the stream data file.
        file_name (str): The name of the stream data file.
        data (numpy.ndarray): The loaded stream data, or `None` if the file was not found.
        config (dict): Parsed tree config captured in the file, or {}.

    Methods:
        load_data(): Loads the stream data from the file specified by `file_path`.
        get_by_index(index): Retrieves a retained instance by its monotonic id.
        get_by_file_name(file_name): Retrieves a retained instance by file name.
    """
    # Bounded registry: retain only the most recent _MAX_INSTANCES instances so
    # a long session (many loaded files) doesn't grow without limit. Note this
    # is what lets already-analyzed StreamData objects be garbage collected.
    _MAX_INSTANCES = 128
    _instances = deque(maxlen=_MAX_INSTANCES)
    # Monotonic id counter for stable per-instance ids (independent of eviction).
    _next_index = 0

    def __init__(self, file_path):
        self.index = StreamData._next_index
        StreamData._next_index += 1
        self.file_path = file_path
        self.file_name = os.path.basename(self.file_path)

        # Parsed tree config captured in the file (channel 255); populated by
        # load_data(). Defaults to empty when there is no file to load.
        self.config = {}

        # Try to load the data from the file
        if os.path.exists(self.file_path):
            self.load_data()
        elif self.file_path:
            raise FileNotFoundError(f"File '{self.file_path}' does not exist.")
        else:
            self.data = None

        # Register (bounded: appending past maxlen evicts the oldest instance).
        StreamData._instances.append(self)

    @classmethod
    def set_max_instances(cls, n):
        """Resize the retained-instance registry (keeps the most recent ``n``)."""
        cls._MAX_INSTANCES = n
        cls._instances = deque(cls._instances, maxlen=n)

    @classmethod
    def get_by_position(cls, position):
        """Retrieve a retained instance by position (``-1`` = most recent).

        This is the ``stream_data_id`` contract used by the analysis functions:
        a position into the retained window, not the monotonic ``index`` id.
        """
        try:
            return cls._instances[position]
        except IndexError:
            raise IndexError(
                f"stream_data_id {position} out of range: only "
                f"{len(cls._instances)} StreamData instance(s) retained "
                f"(max {cls._MAX_INSTANCES}).")

    def load_data(self):
        """
        Loads the stream data from the file specified by `file_path`.
        """
        sr = StreamReader()
        sr.readStream(self.file_path)
        self.data = sr.data
        # Parsed tree config captured in the file (channel 255), or {} if the
        # file has no config frame. Used to derive calibration constants
        # (sample rate, DAC->current) from the capture itself.
        self.config = sr.config

    def __repr__(self):
        return f"<StreamData(index={self.index}, file_path='{self.file_path}', file_name='{self.file_name}')>"

    @classmethod
    def get_by_index(cls, index):
        """
        Retrieve a retained `StreamData` instance by its monotonic ``index`` id.

        Args:
            index (int): The stable id assigned at creation (see ``self.index``).

        Returns:
            StreamData: The retained instance with that id.

        Raises:
            ValueError: If no retained instance has that id (e.g. it was evicted
                once more than _MAX_INSTANCES newer instances were created).
        """
        for obj in cls._instances:
            if obj.index == index:
                return obj
        raise ValueError(
            f"No retained StreamData instance with index {index} "
            f"(only the most recent {cls._MAX_INSTANCES} are kept).")

    @classmethod
    def get_by_file_name(cls, file_name):
        """
        Retrieve a `StreamData` instance by its file name.

        Args:
            file_name (str): The file name of the `StreamData` instance to retrieve.

        Returns:
            StreamData: The `StreamData` instance with the specified file name.

        Raises:
            ValueError: If no `StreamData` instance is found with the specified file name.
        """
        for obj in cls._instances:
            if obj.file_name == file_name:
                return obj
        raise ValueError(f"No StreamData instance found with file name '{file_name}'")

# Need to add outputdir=None feature
def take_raw(col, outputdir=None, synch=False, fadc=125e6, decimation=0, check_delay_sec=0.1, timeout_sec=30.0):
    """
    Capture raw waveform data from a single column of the detector.

    Args:
        col (int): The column number to capture data from.
        synch (bool, optional): If True, trigger a synchronized waveform capture. Otherwise, trigger an asynchronous capture.
        fadc (float, optional): The FADC sampling rate in Hz. Default is 125e6 (125 MHz).
        decimation (int, optional): The decimation factor to apply to the waveform data. Default is 0 (no decimation).
        check_delay_sec (float, optional): The time in seconds to wait between checks for the saved waveform file. Default is 0.1 (100 ms).
        timeout_sec (float, optional): Maximum time in seconds to wait for the waveform file to appear before giving up. Default is 30.0.

    Returns:
        str: The full path to the saved waveform file.

    Raises:
        TimeoutError: If no new waveform file is saved within timeout_sec.
    """
    # Get the last saved raw dataset filename
    last_raw0 = Client.hwg.WaveformCaptureReceiver.LastSavedFileName.get()
    #print(f'last_raw0 = {last_raw0}')

    # Determine the column board to use
    cb = Client.cbs[col // 8]

    # Add this featuer
    # Set the output directory if not provided
    if outputdir is None:
        outputdir = Client.sessiondir

    # Where to save waveforms on disk
    Client.hwg.WaveformCaptureReceiver.SavedFilePath.set(outputdir)
    
    # Enable saving waveform
    Client.hwg.WaveformCaptureReceiver.SaveData.set(True)

    # Configure the waveform capture settings
    cb.DataPath.WaveformCapture.AllChannels.set(False)
    cb.DataPath.WaveformCapture.SelectedChannel.set( ( col % 8 ) )
    cb.DataPath.WaveformCapture.Decimation.set(decimation)
    Client.hwg.WaveformCaptureReceiver.PlotColumn.set( ( col % 8 ) )
    Client.hwg.WaveformCaptureReceiver.PlotWaveform.set(True)

    # Trigger the waveform capture
    if synch:
        cb.WarmTdmCore.Timing.TimingTx.WaveformCapture()
    else:
        cb.DataPath.WaveformCapture.CaptureWaveform()

    # Wait for the waveform to be saved to disk (bounded by timeout_sec)
    last_raw = None
    deadline = time.time() + timeout_sec
    try:
        while True:
            if last_raw is not None:
                #print(f'last_raw = {last_raw}')
                #print(f'os.path.getsize(last_raw) = {os.path.getsize(last_raw)}')
                if last_raw != last_raw0 and os.path.getsize(last_raw) > 0:
                    break
            if time.time() > deadline:
                raise TimeoutError(
                    f"take_raw: no new waveform file for column {col} within "
                    f"{timeout_sec} s (last seen: {last_raw!r}).")
            time.sleep(check_delay_sec)
            last_raw = Client.hwg.WaveformCaptureReceiver.LastSavedFileName.get()
    finally:
        # Always disable waveform capture, even if we timed out
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

    # Enable msec timestamping for hi cadence waveform acquisition
    millisecond_timestamp = Client.hwg.WaveformCaptureReceiver.MillisecondTimestamp
    previous_millisecond_timestamp = millisecond_timestamp.get()
    millisecond_timestamp.set(True)

    wfs = []
    try:
        for ii in range(nraw):
            wfs.append(take_raw(col=col, outputdir=save_dir, synch=synch))
    finally:
        # Restore the previous timestamping mode even if capture fails/interrupted
        millisecond_timestamp.set(previous_millisecond_timestamp)
    idxfn = f'raw_{ctime}.txt'
    idxfp = os.path.join(save_dir, idxfn)
    with open(idxfp, 'w') as f:
        for wf in wfs:
            f.write(f"{wf}\n")

    print(f"{nraw} waveforms indexed to {idxfp} for column {col}.")
    return idxfp

def take_data(acq_time_sec,start_delay_sec=1.):
    was_running=True
    # If not running, start running.
    cb0=Client.cbs[0]
    # If running, end the run.
    if not cb0.WarmTdmCore.Timing.TimingTx.Running.get():
        was_running=False
        cb0.WarmTdmCore.Timing.TimingTx.StartRun()
        time.sleep(start_delay_sec)

    r=Client.client.root
    r.DataWriter.AutoName()
    r.DataWriter.DataFile.set(
        os.path.join(os.path.abspath(Client.sessiondir),r.DataWriter.DataFile.get()))

    data_filename=r.DataWriter.DataFile.get()
    print(f'Open file {data_filename}')
    r.DataWriter.Open()
    print(f'Acquire data for {acq_time_sec} sec ...')
    time.sleep(acq_time_sec)
    print(f'Close file {data_filename}')
    r.DataWriter.Close()

    if not was_running:
        # Maybe the user had a reason for not running.  Return system
        # to them in that state.
        cb0.WarmTdmCore.Timing.TimingTx.EndRun()

    return data_filename
        
#def check_timing(cols=None):
#    """
#    """
#    # If specific columns to check not specified, do all enabled columns
#    if cols is None:
#        col_list=Client.client.root.Group.ColTuneEnable.get()
#        cols = [col for col,enabled in enumerate(col_list) if enabled]
#
#    for col in cols:
#        rawfn=take_raw(col, synch=True, decimation=0)
#        print(rawfn)
