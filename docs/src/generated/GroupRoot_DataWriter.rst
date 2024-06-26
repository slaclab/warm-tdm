****************************
DataWriter
****************************

| Class which stores received data to a file.


Summary
#######

Variable List
*************

* DataFile
* IsOpen
* TotalSize
* FrameCount

Command List
*************

* Open
* Close
* AutoName

Details
#######

Variables
*********

.. topic:: GroupRoot.DataWriter.DataFile

    | Data file for storing frames for connected streams.
    | This is the file opened when the Open command is executed.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |DataFile                                                                                            |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.DataFile                                                                       |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |str                                                                                                 |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |precision                                                                                           |0                                                                                                   |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |mode                                                                                                |RW                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

.. topic:: GroupRoot.DataWriter.IsOpen

    | Status field which is True when the Data file is open.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |IsOpen                                                                                              |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.IsOpen                                                                         |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |enum                                                                                                |{False: 'False', True: 'True'}                                                                      |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |bool                                                                                                |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |enum                                                                                                |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |precision                                                                                           |0                                                                                                   |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |mode                                                                                                |RO                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

.. topic:: GroupRoot.DataWriter.TotalSize

    | Total bytes written.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |TotalSize                                                                                           |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.TotalSize                                                                      |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |UInt64                                                                                              |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |precision                                                                                           |0                                                                                                   |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |mode                                                                                                |RO                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

.. topic:: GroupRoot.DataWriter.FrameCount

    | Total frames received and written.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |FrameCount                                                                                          |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.FrameCount                                                                     |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |UInt32                                                                                              |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |precision                                                                                           |0                                                                                                   |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |mode                                                                                                |RO                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

Commands
********

.. topic:: GroupRoot.DataWriter.Open

    | Open data file.
    | The new file name will be the contents of the DataFile variable.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |Open                                                                                                |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.Open                                                                           |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |int                                                                                                 |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

.. topic:: GroupRoot.DataWriter.Close

    | Close data file.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |Close                                                                                               |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.Close                                                                          |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |int                                                                                                 |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

.. topic:: GroupRoot.DataWriter.AutoName

    | Auto create data file name using data and time.


    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |Field                                                                                               |Value                                                                                               |
    +====================================================================================================+====================================================================================================+
    |name                                                                                                |AutoName                                                                                            |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |path                                                                                                |GroupRoot.DataWriter.AutoName                                                                       |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |typeStr                                                                                             |int                                                                                                 |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+
    |disp                                                                                                |{}                                                                                                  |
    +----------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------+

