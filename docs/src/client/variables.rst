.. Warm TDM documentation master file

===============
Variable Access
===============

The main class which is used in the Warm TDM system is a Rogue Variable which provides in interface to
the running system. Variables can get read from using a get() call, or written to with a set() call.

Get Calls
=========

The following code example show how to read a value from a variable

.. code-block:: python

      ret = GroupRoot.Group.RowTuneEnable.get()


In this example a 64 element array of booleans is returned, indicating the tune enable state of each row in the system.

Alternatively a single array element can be read using the index attribute:

.. code-block:: python

      ret = GroupRoot.Group.RowTuneEnable.get(index=10)

In the above example the enable state of row 10 is returned.


In some cases you may want to read back the current value of a variable without actually reading from the core system. This is sometimes used to see the last read value from hardware without initiating a new read. Thsi is helpfull when creating fast running scripts:

.. code-block:: python

      ret = GroupRoot.Group.RowTuneEnable.value(index=10)


There are situations where you would like to get back formatted string representation of a value. Rogue provides the ability for the developer to specify formatting options in a way to best display data:


.. code-block:: python

      ret = GroupRoot.Group.RowTuneEnable.disp(index=10)

      # Or maybe get the full array, without reading from hardware
      ret = GroupRoot.Group.RowTuneEnable.valueDisp()


In some situations int he Warm TDM system the variable may contain a two dimensional array. Below is an example of getting the Sq1Bias value for a specific row and column:

.. code-block:: python

      row = 5
      col = 10

      ret = GroupRoot.Group.Sq1Bias.get(index=(row,col))

Set Calls
=========

Setting a variable is done in the same way:

.. code-block:: python

      row = 5
      col = 10

      GroupRoot.Group.Sq1Bias.get(value=1.5, index=(row,col))


You can also set back the full two dimensional array:

.. code-block:: python

      sq1b = GroupRoot.Group.Sq1Bias.get()

      sq1b[5][4] = 5.4

      GroupRoot.Group.Sq1Bias.set(value=sq1b)


