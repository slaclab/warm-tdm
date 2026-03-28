import os
import time
import datetime

class Session:
    """Represents a session for organizing and managing data.

    Attributes:
        session (object): The Jupyter session object.
        session_id (str): The session ID.
        datedir (str): The directory for the current date.
        date (str): The current date in the format 'YYYYMMDD'.
        ctime0 (str): The creation time of the current session.
        sessiondir (str): The directory for the current session.
    """
    jupyter_session = None
    jupyter_session_id = None
    datedir = None
    date = None
    ctime0 = None
    sessiondir = None

def new_session(path):
    """Create a new session and set up the necessary directories.

    This function checks the provided path for writing output to for
    write access, and sets up the necessary directories to organize the data
    from the current session.

    If the provided path is not accessible, it defaults to the 'data' directory
    in the parent directory of the current working directory. If that directory
    is also not accessible, it defaults to the '/tmp/' directory.

    Parameters:
        path (str): The path to be used for storing session data.

    Raises:
        OSError: If there is an error creating the date or session directories.
    """
    # Get Jupyter session ID
    import jupyter_client.session
    Session.jupyter_session = jupyter_client.session.Session()
    Session.jupyter_session_id = Session.jupyter_session.session

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
    Session.date = datetime.datetime.now().strftime('%Y%m%d')
    Session.datedir = os.path.join(path, Session.date)
    Session.ctime0 = str(int(time.time()))

    # Create data directory, if it doesn't already exist
    if not os.path.isdir(Session.datedir):
        try:
            os.makedirs(Session.datedir)
        except OSError as e:
            print(f"Error creating date directory '{Session.datedir}': {e}")

    # Create session directory based on creation time
    Session.sessiondir = os.path.join(Session.datedir, f'{Session.ctime0}')
    try:
        os.makedirs(Session.sessiondir, exist_ok=False)
    except OSError as e:
        print(f"Error creating session directory '{Session.sessiondir}': {e}")

    print(f"New session directory created: {Session.sessiondir}")