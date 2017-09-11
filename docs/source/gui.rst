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
saved in the config file for the next startup.

A typical module widget
=======================

The image below shows the module widget for the PID modules. 

.. image:: pid_widget.jpg
   :scale: 100 %
   :alt: A typical module widget
   :align: center

.. automodule:: pyrpl.widgets.module_widgets.base_module_widget

We explain below the operation of the most useful module widgets.


Acquisition Module Widgets
==========================

.. automodule:: pyrpl.widgets.module_widgets.acquisition_module_widget

Scope Widget
------------

The scope widget is represented in the image below

.. image:: scope_widget.jpg
   :scale: 100 %
   :alt: scope module widget
   :align: center

.. automodule:: pyrpl.widgets.module_widgets.scope_widget

Spectrum Analyzer Widget
------------------------

The spectrum analyzer widget is represented in the image below

.. image:: spectrum_analyzer_widget.jpg
   :scale: 100 %
   :alt: scope module widget
   :align: center

.. automodule:: pyrpl.widgets.module_widgets.spec_an_widget

.. warning:: Because the spectrum analyzer uses the data sampled by the scope to perform measurements, 
             it is not possible to use both instruments simultaneaously. When the spectrum-analyzer is running, 
             the scope-widget appears greyed-out to show that it is not available.


Network Analyzer Widget
-----------------------

The network analyzer widget is represented in the image below

.. image:: network_analyzer_widget.jpg
   :scale: 100 %
   :alt: scope module widget
   :align: center

.. automodule:: pyrpl.widgets.module_widgets.na_widget

.. _iq-widget-label:

Iq Widget
---------

The iq widget is represented in the image below. A schematic of the internal connection of the IQ-module can be 
shown or hidden with the arrow button.

.. image:: iq_widget.gif
   :scale: 100 %
   :alt: scope module widget
   :align: center

.. automodule:: pyrpl.widgets.module_widgets.iq_widget