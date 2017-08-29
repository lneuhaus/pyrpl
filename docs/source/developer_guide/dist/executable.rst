How to make a single-file pyrpl executable not depending on a Python installation
****************************************************************************************

In the pyrpl root dir:

::

    conda create -y -n py34 python=3.4 numpy scipy paramiko pandas nose pip pyqt qtpy
    activate py34
    python setup.py develop
    pip install pyinstaller
    pyinstaller --clean --onefile --distpath dist -n pyrpl ./scripts/run_pyrpl.py

We now use spec files in order to include the fpga bitfile in the
bundle. This requires only

::

    pyi-makespec --onefile -n pyrpl ./scripts/run_pyrpl.py
    # add datas section to the file...
    # datas=[('pyrpl/fpga/red_pitaya.bin', 'pyrpl/fpga'),
             ('pyrpl/monitor_server/monitor_server*',
              'pyrpl/monitor_server')],
    pyinstaller pyrpl.spec
