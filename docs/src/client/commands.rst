.. Warm TDM documentation master file

========
Commands
========

Some Devices within the Warm TDM tree contain commands. These classes are used to initiate a short run command which
will return with little delay. Longer operations, such as tuning are organized into Processes which include Start() and Stop()
commands as well as Variable to monitor the status of the process.

Some commands take arguments, others don't. Commands may also return values.

See below for an example of starting a SaTung process.

.. code-block:: python

      GroupRoot.Group.SaTuneProcess.exec()


Here is an example of storing the current configuration to a file:

.. code-block:: python

      GroupRoot.SaveConfig.exec('path_to_config.yml')


You can also get the current configuration returned as a string:


.. code-block:: python

      config = GroupRoot.GetYamlCOnfig.exec()


