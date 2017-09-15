API manual
**************

This manual will guide you step-by-step through the programming interface of each PyRPL modules.

1 First steps
=================

If the installation went well, you should now be able to load the
package in python. If that works you can pass directly to the next
section 'Connecting to the RedPitaya'.

.. code:: python

    from pyrpl import Pyrpl

Sometimes, python has problems finding the path to pyrpl. In that
case you should add the pyrplockbox directory to your pythonpath
environment variable
(http://stackoverflow.com/questions/3402168/permanently-add-a-directory-to-pythonpath).
If you do not know how to do that, just manually navigate the ipython
console to the directory, for example:

.. code:: python

    cd c:\lneuhaus\github\pyrpl

Now retry to load the module. It should really work now.

.. code:: python

    from pyrpl import Pyrpl

Connecting to the RedPitaya
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You should have a working SD card (any version of the SD card content is
okay) in your RedPitaya (for instructions see
http://redpitaya.com/quick-start/). The RedPitaya should be connected
via ethernet to your computer. To set this up, there is plenty of
instructions on the RedPitaya website
(http://redpitaya.com/quick-start/). If you type the ip address of your
module in a browser, you should be able to start the different apps from
the manufacturer. The default address is http://192.168.1.100. If this
works, we can load the python interface of pyrplockbox by specifying the
RedPitaya's ip address.

.. code:: python

    HOSTNAME = "192.168.1.100"

.. code:: python

    from pyrpl import Pyrpl
    p = Pyrpl(hostname=HOSTNAME)
   
If you see at least one '>' symbol, your computer has successfully
connected to your RedPitaya via SSH. This means that your connection
works. The message 'Server application started on port 2222' means that
your computer has sucessfully installed and started a server application
on your RedPitaya. Once you get 'Client started with success', your
python session has successfully connected to that server and all things
are in place to get started.


Basic communication with your RedPitaya
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

    # Access the RedPitaya object in charge of communicating with the board
    r = p.rp

    #check the value of input1
    print r.scope.voltage1

With the last command, you have successfully retrieved a value from an
FPGA register. This operation takes about 300 µs on my computer. So
there is enough time to repeat the reading n times.

.. code:: python

    #see how the adc reading fluctuates over time
    import time
    from matplotlib import pyplot as plt
    times, data = [],[]
    t0 = time.time()
    n = 3000
    for i in range(n):
        times.append(time.time()-t0)
        data.append(r.scope.voltage_in1)
    print("Rough time to read one FPGA register: ", (time.time()-t0)/n*1e6, "µs")
    %matplotlib inline
    f, axarr = plt.subplots(1,2, sharey=True)
    axarr[0].plot(times, data, "+")
    axarr[0].set_title("ADC voltage vs time")
    axarr[1].hist(data, bins=10,normed=True, orientation="horizontal")
    axarr[1].set_title("ADC voltage histogram")

You see that the input values are not exactly zero. This is normal with
all RedPitayas as some offsets are hard to keep zero when the
environment changes (temperature etc.). So we will have to compensate
for the offsets with our software. Another thing is that you see quite a
bit of scatter beetween the points - almost as much that you do not see
that the datapoints are quantized. The conclusion here is that the input
noise is typically not totally negligible. Therefore we will need to use
every trick at hand to get optimal noise performance.

After reading from the RedPitaya, let's now try to write to the register
controlling the first 8 yellow LED's on the board. The number written to
the LED register is displayed on the LED array in binary representation.
You should see some fast flashing of the yellow leds for a few seconds
when you execute the next block.

.. code:: python

    #blink some leds for 5 seconds
    from time import sleep
    for i in range(1025):
        r.hk.led=i
        sleep(0.005)

.. code:: python

    # now feel free to play around a little to get familiar with binary representation by looking at the leds.
    from time import sleep
    r.hk.led = 0b00000001
    for i in range(10):
        r.hk.led = ~r.hk.led>>1
        sleep(0.2)

.. code:: python

    import random
    for i in range(100):
        r.hk.led = random.randint(0,255)
        sleep(0.02)

2 RedPitaya (or Hardware) modules
==================================

Let's now look a bit closer at the class RedPitaya. Besides managing the
communication with your board, it contains different modules that
represent the different sections of the FPGA. You already encountered
two of them in the example above: "hk" and "scope". Here is the full
list of modules:

.. code:: python

    r.hk #"housekeeping" = LEDs and digital inputs/outputs
    r.ams #"analog mixed signals" = auxiliary ADCs and DACs.
    
    r.scope #oscilloscope interface
    
    r.asg0 #"arbitrary signal generator" channel 0
    r.asg1 #"arbitrary signal generator" channel 1
    
    r.pid0 #first of three PID modules
    r.pid1
    r.pid2
    
    r.iq0 #first of three I+Q quadrature demodulation/modulation modules
    r.iq1
    r.iq2
    
    r.iir #"infinite impulse response" filter module that can realize complex transfer functions


ASG and Scope module
~~~~~~~~~~~~~~~~~~~~~~

Arbitrary Signal Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyrpl.hardware_modules.asg

Oscilloscope
~~~~~~~~~~~~

.. automodule:: pyrpl.hardware_modules.scope


PID module
~~~~~~~~~~

.. automodule:: pyrpl.hardware_modules.pid

IQ module
~~~~~~~~~~

.. automodule:: pyrpl.hardware_modules.iq

IIR module
~~~~~~~~~~

.. automodule:: pyrpl.hardware_modules.iir


3 Pyrpl (or Software) modules
==================================

Software modules are modules that don't have an FPGA counterpart. They are directly accessible at the root pyrpl object
(no need to go through the redpitaya object). We have already encountered a software module above. Remember how we accessed the 
network analyzer module:

.. code:: python
    
     HOSTNAME = "192.168.1.100"
     from pyrpl import Pyrpl
     p = Pyrpl(hostname=HOSTNAME)

     # hardware modules are members of the redpitaya object
     p.rp.iq0

     # software modules are members of the root pyrpl object
     p.networkanalyzer

Software modules usually perform higher-level tasks than hardware modules. Moreover, accessing a hardware module without
care could be harmful to some acquisition already running on the redpitaya. For this reason, it is advisable to access hardware modules 
via module managers only.

Using Module Managers
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyrpl.software_modules.module_managers

Spectrum Analyzer
~~~~~~~~~~~~~~~~~~~

.. automodule:: pyrpl.software_modules.spectrum_analyzer

Lockbox
~~~~~~~~~

Coming soon