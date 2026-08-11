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
