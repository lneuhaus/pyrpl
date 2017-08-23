Common installation problems
******************************


.. _anaconda_problems:

Common issues with Anaconda
===============================

Problem: The ``conda`` command does not work
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reason:

    The default installation of Anaconda in Windows does not add the conda to the PATH environment variable. Therefore, the windows terminal does not find the program by default. To make it work:

Solution:

    * Execute the following command in your terminal to activate the conda environment: :code:`C:\Users\YOUR_USERNAME\Anaconda3\Scripts\activate`. Of course, you should insert your own username, and possibly replace the initial part of the command with the actual conda installation directory on your computer. After this, the conda command should also work without problems.
    * Another solution is to execute the Anaconda navigator, click on the left on "Environments", left-click on the arrow next to "root" in the list of environments, and click on "Open Terminal". In the terminal that opens, the conda command should now work such that you can install the PyRPL dependencies.


Problem: I cannot launch PyRPL, even though the installation finished successfullly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reason:

    The installation created the `virtual environment <https://conda.io/docs/using/envs.html>`__ "pyrpl-env" to install all required pyrpl dependencies in. When trying to launch PyRPL, you must do so from this virtual env.

Solution:

    Make sure that you are in the virtual environment pyrpl-env. This can be accomplished by various ways:

        * Launch Jupyter console or notebook from the Anaconda navigator after having selected the pyrpl-env environment and load pyrpl from there.
        * Execute the following command in your terminal to activate the pyrpl-env environment: :code:`C:\Users\YOUR_USERNAME\Anaconda3\Scripts\activate pyrpl-env`. Of course, you should insert your own username, and possibly replace the initial part of the command with the actual conda installation directory on your computer. After this, load Python, Jupyter, Ipython or the notebook as usual from the same terminal.
        * Change the path in the batch file / link that you use to launch python. Instead of calling the executables in :code:`C:\Users\YOUR_USERNAME\Anaconda3\Scripts\*` or the equivalent directory on your computer, use the ones in :code:`C\UsersYOUR_USERNAME\Anaconda3\envs\pyrpl-env\Scripts\*`. Your python terminal will be directly in the right environment 'pyrpl-env'.
