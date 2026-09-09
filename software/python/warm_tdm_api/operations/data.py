from .streamreader import StreamReader

import os
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
        # PID-debug timeseries (channels 0-7); populated by load_data().
        self.pid = {}

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
        # PID-debug timeseries pid[col][row][field] from the same read (channels
        # 0-7); empty if the run had PidDebugEnable off. Exposed as data model #3
        # via PidDebugData (see pid_data()); kept here so one file read yields
        # both the readout and the PID-debug streams.
        self.pid = sr.pid
        # Parsed tree config captured in the file (channel 255), or {} if the
        # file has no config frame. Used to derive unit-conversion factors
        # (sample rate, DAC->current) from the capture itself.
        self.config = sr.config

    def pid_data(self):
        """Return a PidDebugData view over this file's PID-debug stream.

        No second file read -- it wraps the ``pid`` dict already decoded by
        load_data(). Returns a registered PidDebugData (so plot_pid_debug's
        ``-1`` most-recent contract works).
        """
        return PidDebugData.from_stream_data(self)

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


class PidDebugData:
    """Container for a capture's PID-debug stream (data model #3).

    Parallel to StreamData, but for the per-column PID-debug channels (0-7)
    rather than the channel-9 readout. Holds ``pid[col][row][field]`` timeseries
    (accumError, sumAccumError, pidResult, sq1FbEnd, numFluxJumps, ... -- see
    warm_tdm._DataFormats.PID_DEBUG_FIELDS) for servo diagnostics.

    Construct from a file path (loads it) or, preferably, from an existing
    StreamData via ``from_stream_data`` / ``StreamData.pid_data()`` so a single
    file read yields both the readout and the PID-debug streams. Keeps the same
    bounded recent-instance registry + position contract as StreamData, so
    plot_pid_debug's ``-1`` = most recent works.

    Attributes:
        index (int): stable monotonic id assigned at creation.
        file_path / file_name (str): source file (may be '' if wrapped).
        pid (dict): pid[col][row][field] -> list of samples.
        config (dict): parsed tree config captured in the file, or {}.
    """
    _MAX_INSTANCES = 128
    _instances = deque(maxlen=_MAX_INSTANCES)
    _next_index = 0

    def __init__(self, file_path='', _pid=None, _config=None, _file_name=None):
        self.index = PidDebugData._next_index
        PidDebugData._next_index += 1
        self.file_path = file_path
        self.file_name = _file_name if _file_name is not None else os.path.basename(file_path)

        if _pid is not None:
            # Wrapping an already-read stream (no second file read).
            self.pid = _pid
            self.config = _config if _config is not None else {}
        elif os.path.exists(file_path):
            sr = StreamReader()
            sr.readStream(file_path)
            self.pid = sr.pid
            self.config = sr.config
        elif file_path:
            raise FileNotFoundError(f"File '{file_path}' does not exist.")
        else:
            self.pid = {}
            self.config = {}

        PidDebugData._instances.append(self)

    @classmethod
    def from_stream_data(cls, sd):
        """Wrap a StreamData's already-decoded PID stream (no re-read)."""
        return cls(file_path=sd.file_path, _pid=sd.pid, _config=sd.config,
                   _file_name=sd.file_name)

    @classmethod
    def set_max_instances(cls, n):
        """Resize the retained-instance registry (keeps the most recent ``n``)."""
        cls._MAX_INSTANCES = n
        cls._instances = deque(cls._instances, maxlen=n)

    @classmethod
    def get_by_position(cls, position):
        """Retrieve a retained instance by position (``-1`` = most recent)."""
        try:
            return cls._instances[position]
        except IndexError:
            raise IndexError(
                f"pid_data_id {position} out of range: only "
                f"{len(cls._instances)} PidDebugData instance(s) retained "
                f"(max {cls._MAX_INSTANCES}).")

    def __repr__(self):
        ncols = len(self.pid)
        return (f"<PidDebugData(index={self.index}, file_name='{self.file_name}', "
                f"cols={sorted(self.pid)})>" if ncols else
                f"<PidDebugData(index={self.index}, file_name='{self.file_name}', empty)>")
