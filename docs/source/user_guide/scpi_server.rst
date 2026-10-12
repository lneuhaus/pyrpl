Read-only SCPI server
*********************

PyRPL controls the Red Pitaya through ``monitor_server``, which accepts a
single client. To let another acquisition program read the DSP signals while
PyRPL runs the lockbox, PyRPL can start a second, read-only server on the
board: ``pyrpl_scpi_server``.

* It never writes to the FPGA (``/dev/mem`` is mapped read-only), so it cannot
  disturb the lockbox, the scope or the PyRPL GUI.
* Several programs can connect at the same time. Each connection has its own
  trigger settings.
* It speaks SCPI-style text over TCP, by default on port 5000 like the stock
  Red Pitaya SCPI server. Any language with sockets or VISA can use it.
* It reads the instantaneous value of every DSP signal of the loaded FPGA
  profile (``in1``, ``in2``, ``out1``, ``out2``, ``pid0``, ``iq0``, ...), the
  same values as ``RedPitaya.sampler``.

.. warning::

   Do not run the stock Red Pitaya SCPI server together with PyRPL: it
   expects the stock FPGA image and writes to registers that belong to the
   PyRPL DSP modules. PyRPL stops it when it starts ``pyrpl_scpi_server``.

Starting the server
===================

Enable it in the ``redpitaya`` section of the configuration file, or as an
argument::

    from pyrpl import Pyrpl
    p = Pyrpl(config="my_lockbox", scpi_server=True, scpi_port=5000)

PyRPL uploads the server, starts it in the background and leaves it running
when PyRPL exits, so that the acquisition program keeps its connection. A new
PyRPL session reuses the running server if its settings did not change. The
server, and all its connections, are stopped before PyRPL reprograms the FPGA,
because reading FPGA registers during reprogramming can freeze the board.
PyRPL restarts it with the signal list of the new profile afterwards.

To start it by hand (``ssh root@rp-xxxxxx.local``)::

    /opt/pyrpl/pyrpl_scpi_server -p 5000 &

Without ``-s`` the server offers the full PyRPL signal list. Stop it with
``killall pyrpl_scpi_server``.

Python client
=============

``pyrpl/scpi_client.py`` only depends on numpy and the standard library; it
can be copied into a program that does not install PyRPL::

    from pyrpl.scpi_client import ScpiClient

    with ScpiClient("rp-xxxxxx.local") as rp:
        print(rp.idn, rp.signals)
        in1, pid0 = rp.values("in1", "pid0")            # read back to back
        mean_std_min_max = rp.stats(0.1, "in1")         # 100 ms on the board

        # 1000 points every 10 us, starting on a rising edge of DIO0_P
        rp.set_trigger("DIO0_P", edge="rising", timeout=5.0, delay=0.0)
        t, (in1, pid0) = rp.acquire(1000, 10e-6, "in1", "pid0")

With pyvisa::

    import pyvisa
    rp = pyvisa.ResourceManager().open_resource(
        "TCPIP::rp-xxxxxx.local::5000::SOCKET",
        read_termination="\r\n", write_termination="\n")
    rp.query("SIG:VAL? in1,pid0")

Commands
========

Commands are case insensitive and accept the short (upper case) or long form
of each keyword. Several commands can be sent on one line, separated by
``;``; their answers are then separated by ``;``. Answers end with ``\r\n``.
Values are in PyRPL units: a raw value of 8191 (2\ :sup:`13`-1) reads as 1.0.

A query that fails answers ``ERR!`` so that the client stays in sync; the
reason is returned by ``SYSTem:ERRor?``.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``*IDN?``
     - ``PYRPL,pyrpl_scpi_server,<fpga profile>,<server version>``
   * - ``*RST``, ``*CLS``
     - reset the trigger settings and the error queue / clear the error queue
   * - ``SYSTem:ERRor?``
     - next error, ``0,"No error"`` if none
   * - ``SIGnal:LIST?``
     - signals of the loaded FPGA profile, ``in1,in2,out1,...``
   * - ``SIGnal:VALue? <sig>[,<sig>...]``
     - current values, read back to back (about 1 µs apart)
   * - ``SIGnal:RAW? <sig>[,<sig>...]``
     - current raw values, signed 14 bit integers
   * - ``SIGnal:STATistics? <duration>,<sig>[,<sig>...]``
     - samples as fast as possible during ``duration`` seconds and returns
       ``mean,std,min,max`` for each signal
   * - ``SIGnal:ACQuire? <n>,<interval>,<sig>[,<sig>...]``
     - ``n`` points, one every ``interval`` seconds (0: as fast as possible),
       after the trigger if one is set. Returns ``n`` rows
       ``t,<sig1>,<sig2>,...`` flattened in one line, ``t`` in seconds from
       the trigger edge. At most 10\ :sup:`6` values per acquisition.
   * - ``SIGnal:ACQuire:AVERage ON|OFF``
     - with ``ON``, each point of ``SIGnal:ACQuire?`` is the mean of all the
       samples taken during its interval (the board samples as fast as it
       can), and ``t`` is the centre of the interval. The intervals follow
       each other without gap. Needs an interval > 0 (default ``OFF``)
   * - ``TRIGger:SOURce NONE|DIO0_P...DIO7_P|DIO0_N...DIO7_N``
     - trigger of ``SIGnal:ACQuire?`` (default ``NONE``)
   * - ``TRIGger:EDGE RISing|FALLing|BOTH``
     - edge of the trigger pin (default ``RISING``)
   * - ``TRIGger:TIMeout <s>``
     - maximum wait for the edge, 0 waits forever (default 1 s). On timeout
       the acquisition answers ``ERR!`` with error ``-200,"Trigger timeout"``
   * - ``TRIGger:DELay <s>``
     - time between the edge and the first point (default 0)
   * - ``DIGital:PIN? <pin>``, ``DIGital:PIN:DIRection? <pin>``
     - state (0/1) and direction (``IN``/``OUT``) of a digital pin, read only

Every setting command has a query form, for example ``TRIGger:SOURce?``.

Timing
------

The trigger and the sampling are done in software on the ARM processor: the
server polls the pin at a few MHz and reads the signals right after the edge.
The latency between the edge and the first point is typically around 1 µs,
with occasional outliers of tens of µs when Linux schedules another task.
The ``t`` column reports the measured time of each point. While waiting for a
trigger, the server keeps one CPU core busy. For hardware-timed, gap-free
traces use the PyRPL scope instead.

Signal plotter
==============

The ``SignalPlotter`` software module (``p.signalplotter``, also a tab of the
GUI) plots DSP signals over long periods through this server: any number of
signals, one point every ``interval`` (100 µs to hours), each point being the
mean over its interval (``SIGnal:ACQuire:AVERage ON``). It starts the server
on the Red Pitaya when needed.

* ``mode = "continuous"``: strip chart of the last ``duration`` seconds. The
  data is read in blocks of about 0.25 s, leaving a gap of about one network
  round trip (~1 ms) between blocks.
* ``mode = "triggered"``: each edge on ``trigger_source`` starts a block of
  ``points`` points (after ``trigger_delay``); the last block is shown and the
  plotter re-arms for the next edge.

``save_curve`` stores the data in PyRPL's curve database, one curve per
signal (the first one is the parent of the others). From Python::

    p.signalplotter.channels = ["in1", "pid0", "iq0"]
    p.signalplotter.interval = 0.01
    p.signalplotter.start()
    ...
    p.signalplotter.stop()
    t, pid0 = p.signalplotter.times, p.signalplotter.data["pid0"]

Older configuration files list the software modules to load: add
``SignalPlotter`` to the ``modules`` list of the ``pyrpl`` section to get it.
With a simulated Red Pitaya (hostname ``_FAKE_``) it plots simulated data.

Building the server
===================

The binary ``pyrpl/monitor_server/pyrpl_scpi_server`` is shipped with PyRPL.
It is linked statically, so it runs on every Red Pitaya OS version. To
rebuild it on Windows with the ARM compiler of Vitis 2024.2, run
``pyrpl\monitor_server\make_scpi_server.bat``; on Linux run
``make pyrpl_scpi_server`` in the same folder.

The unit tests ``pyrpl/test/test_scpi_server.py`` compile the server with the
host ``gcc`` and run it with ``-m <file>``, which maps a regular file instead
of ``/dev/mem``. They only run on Linux or macOS.
