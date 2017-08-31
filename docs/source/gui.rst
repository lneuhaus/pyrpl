GUI instruments manual
*************************

In this section, we show how to control the main modules of Pyrpl with the Graphical User Interface.

Starting the GUI
================

To start pyrpl's GUI, simply create a Pyrpl object. 


.. code-block:: python

    # import pyrpl library
    import pyrpl

    # create a Pyrpl object and store the configuration in a file 'filter-cavity.yml'
    # by default, the parameter 'gui' is set to True
    p = pyrpl.Pyrpl(config='filter-cavity') 


If you are using the file 'filter-cavity.yml' for the first time, a screen will pop-up
asking you to choose among the different RedPitayas connected to your local network. After that, 
the main Pyrpl widget should appear:

.. image:: pyrpl_widget.jpg
   :scale: 100 %
   :alt: The main pyrpl widget
   :align: center

The main pyrpl widget is initially empty, however, you can use the "modules" menu to populate it 
with module widgets. The module widgets can be closed or reopened at any time, docked/undocked 
from the main module window by drag-and-drop on their sidebar, and their position on screen will be
saved in the config file for latter use.

A typical module widget
=======================

The image below shows the module widget for the PID modules. 

.. image:: pid_widget.jpg
   :scale: 100 %
   :alt: A typical module widget
   :align: center

Above each module widget, one can find a short menu with the following entries:

- Load: Loads the state of the module from a list of previously saved states
- Save: Saves the state with a given name
- Erase: Erases one of the previously saved state
- Edit: Opens a text window to edit the yml code of the required state
- Hide/Show: Hide or show the content of the module widget

Inside the module widget, the different attribute values can be manipulated using the
provided widgets. The modifications will take effect immediately and only affect the 
<current state> untill the current state is saved for latter use.

At the next startup with the same config file, the <current state> of all modules is loaded.
We explain below the operation of the most useful module widgets.

Acquisition Module Widgets
==========================

Acquisition modules are the modules used to acquire data from the redpitaya. At the moment, they 
include the Scope, Network Analyzer and the Spectrum Analyzer. All the acquisition modules have in common 
a plot area where the data are displayed, and a control panel below the plot area.

.. image:: scope_widget.jpg
   :scale: 100 %
   :alt: scope module widget
   :align: center

The different buttons in the control panel are:

- trace_average: chooses the number of successive traces to average together
- curve_name: name of the next saved curve
- run_single: a single acquisition of 'trace_average' traces is started
- run_continuous: a running average with a typical decay constant of 'trace_average' is started
- restart_averaging:
