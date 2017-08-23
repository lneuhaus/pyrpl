Installing PyRPL
*********************************


Option 1: Using pip
===================

If you have pip correctly installed, executing the following line in a command line should install pyrplockbox and all dependencies::

    pip install pyrpl


Option 2: From GitHub using setuptools (beta version)
=====================================================

Download the code manually from https://github.com/lneuhaus/pyrpl/archive/master.zip and unzip it or get it directly from git by typing ::

git clone https://github.com/lneuhaus/pyrpl.git YOUR_DESTINATIONFOLDER

In a command line shell, navigate into your new local pyrplockbox directory and execute ::

python setup.py install 

This copies the files into the side-package directory of python. The setup should make sure that you have the python libraries `paramiko <http://www.paramiko.org/installing.html>`_ and `scp <https://pypi.python.org/pypi/scp>`_ installed. If this is not the case you will get a corresponding error message in a later step of this tutorial.

Option 3: Simple clone from GitHub (developers)
===============================================

If instead you plan to synchronize with github on a regular basis, you can also leave the downloaded code where it is and add the parent directory of the pyrpl folder to the PYTHONPATH environment variable as described in this `thread <http://stackoverflow.com/questions/3402168/permanently-add-a-directory-to-pythonpath>`_. For all beta-testers and developers, this is the preferred option. So the typical PYTHONPATH environment variable should look somewhat like this::

PYTHONPATH=C:\OTHER_MODULE;C:\GITHUB\PYRPL 

If you are experiencing problems with the dependencies on other python packages, executing the following command in the pyrpl directory might help ::

   python setup.py install develop 

If at a later point, you have the impression that updates from github are not reflected in the program's behavior, try this ::

    import pyrpl
    print(pyrpl.__file__)

Should the directory not be the one of your local github installation, you might have an older version of pyrpl installed. 
Just delete any such directories other than your principal github clone and everything should work.



