.. Warm TDM documentation master file

==============
Tree Structure
==============

The elements of the Warm TDM software are arranged in a tree structure, with the GroupRoot class at the base. Each element in the tree can be
accessed by referencing the full path to the element:

..
   GroupRoot.Group.SaTuneProcess.Running.get()

The Warm TDM system is built up of hardware structured in "Groups". Each group consists
of a number of Row boards (typically 2) and colum boards (typically 4). This Group of boards is managed as a
single unit. The entry point in the Warm TDM software is a Root class from the Rogue framework. The GroupRoot
object is the Warm TDM represenation of this Root element and is the starting point for all accesses to the
element in the Warm TDM system.

Currently each GroupRoot manages a single Group. This may change in the future.


.. toctree::
   :maxdepth: 1
   :caption: Contents:

   generated/GroupRoot

The Rogue framework consists of managed elements called Devices, which contain Variable and Commands. Some Devices are designed
to host long running scripts, such as Tuning operations. This are called Processes.

