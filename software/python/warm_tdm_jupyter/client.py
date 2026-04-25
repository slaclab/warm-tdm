import re
import os
import time
import datetime
import subprocess

class Client:
    """Represents a client for interacting with the SLAC warm electronics.

    Attributes:
        client (object): The client object.
        hwg (object): The hardware group object.
        cbs (dict): A dictionary mapping column board indices to column board objects.
        rbs (dict): A dictionary mapping row board indices to row board objects.
        rdds (dict): A dictionary mapping row board indices to row DAC driver objects.
    """
    client = None
    hwg = None
    cbs = {}
    rbs = {}
    rdds = {}

    @classmethod
    def set_client(cls, client, path='/data/warm_tdm/'):
        """Set the client and initialize related attributes.

        This function sets the client, creates a new session, and initializes the related
        attributes such as the hardware group, column boards, row boards, and row DAC
        drivers.

        Parameters:
            client (object): The client object to be set.
            path (str, optional): The path for the new session, defaults to '/data/warm_tdm/'.

        Raises:
            AttributeError: If expected attributes cannot be found in the provided client 
            object's hardware group.
        """
        cls.new_session(path=path)
        cls.client = client
        cls.hwg = client.root.Group.HardwareGroup
        cls.cbs = {int(match.group(2)): getattr(cls.hwg, match.group(1))
                   for hwg_entry in dir(cls.hwg)
                   for match in [re.match(r'(ColumnBoard\[(\d+)\])', hwg_entry)]
                   if match}
        cls.rbs = {int(match.group(2)): getattr(cls.hwg, match.group(1))
                   for hwg_entry in dir(cls.hwg)
                   for match in [re.match(r'(RowBoard\[(\d+)\])', hwg_entry)]
                   if match}
        cls.rdds = {k: cls.rbs[k].RowDacDriver for k in cls.rbs.keys()}

    @classmethod
    def get_client(cls):
        """Get the client object.

        Returns:
            object: The client object.
        """
        return cls.client

    @classmethod
    def new_session(cls, path):
        """Create a new session and set up the necessary directories.

        This function checks the provided path for writing output to for
        write access, and sets up the necessary directories to organize the data
        from the current session.

        If the provided path is not accessible, it defaults to the 'data' directory
        in the parent directory of the current working directory. If that directory
        is also not accessible, it defaults to the user's home directory.

        Parameters:
            path (str): The path to be used for storing session data.

        Raises:
            OSError: If there is an error creating the date or session directories.
        """
        # Get Jupyter session ID
        import jupyter_client.session
        cls.jupyter_session = jupyter_client.session.Session()
        cls.jupyter_session_id = cls.jupyter_session.session

        # Check if path exists and is writable
        if os.path.isdir(path) and os.access(path, os.W_OK):
            pass
        else:
            print(f"Warning: path '{path}' requested for writing data does not exist or is not writable.")

            # Default path to local warm_tdm/software/data directory
            cwd = os.getcwd()
            path = os.path.join(os.path.dirname(cwd), 'data')

            # Check if path exists and is writable
            if os.path.isdir(path) and os.access(path, os.W_OK):
                pass
            else:
                print(f"Warning: fallback '{path}' requested for writing data also does not exist or is not writable.")
                print(f"Warning: Defaulting to writing data to {os.path.expanduser('~')}.")
                path = os.path.expanduser("~")

        # Set up session-specific variables
        cls.date = datetime.datetime.now().strftime('%Y%m%d')
        cls.datedir = os.path.join(path, cls.date)
        cls.ctime0 = str(int(time.time()))

        # Create data directory, if it doesn't already exist
        if not os.path.isdir(cls.datedir):
            try:
                os.makedirs(cls.datedir)
            except OSError as e:
                print(f"Error creating date directory '{cls.datedir}': {e}")

        # Create session directory based on creation time
        cls.sessiondir = os.path.join(cls.datedir, f'{cls.ctime0}')
        try:
            os.makedirs(cls.sessiondir, exist_ok=True)
        except OSError as e:
            print(f"Error creating session directory '{cls.sessiondir}': {e}")

        print(f"New session directory created: {cls.sessiondir}")
