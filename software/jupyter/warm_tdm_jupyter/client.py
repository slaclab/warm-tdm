import re
from .utils import Session,new_session

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

def set_client(client, path='/data/warm_tdm/'):
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
    new_session(path=path)
    Client.client = client
    Client.hwg = client.root.Group.HardwareGroup
    Client.cbs = {int(match.group(2)): getattr(Client.hwg, match.group(1))
                  for hwg_entry in dir(Client.hwg)
                  for match in [re.match(r'(ColumnBoard\[(\d+)\])', hwg_entry)]
                  if match}
    Client.rbs = {int(match.group(2)): getattr(Client.hwg, match.group(1))
                  for hwg_entry in dir(Client.hwg)
                  for match in [re.match(r'(RowBoard\[(\d+)\])', hwg_entry)]
                  if match}
    Client.rdds = {k: Client.rbs[k].RowDacDriver for k in Client.rbs.keys()}

def get_client():
    """Get the client object.

    Returns:
        object: The client object.
    """
    return Client.client