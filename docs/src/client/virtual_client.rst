.. _interfaces_clients_virtual:

========================
Virtual Client Interface
========================

The VirtualClient class in Rogue provides a client interface to a running Rogue server
which replicated the Devices, Variables and Commands that are present on the server.
This class is used for DAQ interfaces, for GUIs and for test scripts.

Below is an example of using the VirtualClient in a python script:

.. code-block:: python

   with pyrogue.interfaces.VirtualClient(addr="localhost",port=9099) as client:

      # Get the reference to the root node
      GroupRoot = client.root

      # Get a variable value
      ret = GroupRoot.Group.NumRowBoards.get()

      # Set a variable value
      GroupRoot.Group.RowTuneEnable.set([True for i in range(64)])

      # Issue a command
      GroupRoot.Group.SaTuneProcess.Start()

      # Issue a command with an arg
      GroupRoot.LoadConfig('config.yml')


The VirtualClient provides access to all of the attributes to the Rogue classes:

.. code-block:: python

   print(f"Type  = {GroupRoot.NumRowBoards.typeStr}")
   print(f"Mode  = {GroupRoot.NumRowBoards.mode}")
   print(f"Units = {GroupRoot.NumRowBoards.units}")
   print(f"Min   = {GroupRoot.NumRowBoards.minimum}")
   print(f"Max   = {GroupRoot.NumRowBoards.maximum}")

Update callbacks can be attached to a Variable as in the Rogue tree:

.. code-block:: python

   def listener(path,varValue):
      print(f"{path} = {varValue.value}")

   GroupRoot.Group.SaTuneProcess.Running.addListener(listener)

The VariableWait helper function can also be used.

.. code-block:: python

   # Wait for the SaTune process to complete
   pyrogue.VariableWait(GroupRoot.Group.SaTuneProcess.Running, lambda varValues: varValues['GroupRoot.Group.SaTuneProcess.Running'].value == False)

The VirtualClient maintains a connection to the Rogue core. The status of this connection
can be directly accessed through the linked attribute. Additionally a callback function
can be added to be called any time the link state changes.

.. code-block:: python

   # create a callback function to be notified of link state changes
   def linkMonitor(state):
      print(f"Link state is now {state}")

   # Add a link monitor
   client.addLinkMonitor(linkMonitor)

   # Remove a link monitor
   client.remLinkMonitor(linkMonitor)

   # Get the current link state
   print(f"Current link state is {client.linked}")


Rogue Documentation
=========================

The Rogue documentation on the VirtualClient can be found here:

Rogue VirtualClient https://slaclab.github.io/rogue/interfaces/clients/virtual.html

