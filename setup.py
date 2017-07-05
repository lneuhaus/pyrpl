# note to the developer
# do not forget to make source distribution with
# python setup.py sdist

# much of the code here is from
# https://jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/

#! /usr/bin/env python
from __future__ import print_function
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from distutils.core import setup
import io
import codecs
import os
import sys



# Version info -- read without importing
_locals = {}
with open('pyrpl/_version.py') as fp:
    exec(fp.read(), None, _locals)
version = _locals['__version__']


# # read requirements
# # from http://stackoverflow.com/questions/14399534/how-can-i-reference-requirements-txt-for-the-install-requires-kwarg-in-setuptool
# requirements = []
# here = os.path.abspath(os.path.dirname(__file__))
# with open(os.path.join(here, 'requirements.txt')) as f:
#     lines = f.readlines()
#     for line in lines:
#         line = line.strip()
#         if '#' not in line and line:
#             requirements.append(line.strip())
requirements = ['scp',
                #'matplotlib', # optional requirementm, not needed for core
                'scipy',
                'pyyaml',
                #'ruamel.yaml' # temporarily disabled
                'pandas',
                'pyqtgraph',
                'numpy>=1.9',
                'paramiko>=2.0',
                'nose>=1.0',
                'qtpy']
if sys.version_info >= (3,4):  # python version dependencies
    requirements += ['quamash']
else:  # python 2.7
    requirements += ['futures']

# cannot install pyQt4 with pip:
# http://stackoverflow.com/questions/4628519/is-it-possible-to-require-pyqt-from-setuptools-setup-py
# PyQt4


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read() 

class PyTest(TestCommand):
    # user_options = [('pytest-args=', 'a', "192.168.1.100")] #not yet working

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

def compile_fpga(): #vivado 2015.4 must be installed for this to work
    cwd = os.getcwd()
    try:
        os.chdir("pyrpl//fpga")
        os.system("make")
    finally:
        os.chdir(cwd)

def compile_server(): #gcc crosscompiler must be installed for this to work
    cwd = os.getcwd()
    try:
        os.chdir("pyrpl//monitor_server")
        os.system("make clean")
        os.system("make")
    finally:
        os.chdir(cwd)

setup(name='pyrpl',
      version=version,
      description='DSP servo controller for quantum optics with the RedPitaya',
      long_description=read('README.md'),
      author='Leonhard Neuhaus',
      author_email='neuhaus@spectro.jussieu.fr',
      url='https://www.github.com/lneuhaus/pyrpl/',
      license='GPLv3',
      classifiers=['Programming Language :: Python :: 2.7',
                   'Natural Language :: English',
                   'Development Status :: 4 - Beta',
                   'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                   'Topic :: Scientific/Engineering :: Human Machine Interfaces',
                   'Topic :: Scientific/Engineering :: Physics',
                   'Programming Language :: C'],
      keywords='RedPitaya DSP FPGA IIR PDH synchronous detection filter PID '
               'control lockbox servo feedback lock quantum optics',
      platforms='any',
      packages=['pyrpl'],
      package_data={'pyrpl': ['fpga/red_pitaya.bin',
                              'monitor_server/monitor_server',
                              'monitor_server/monitor_server_0.95']},

      install_requires=requirements,
      # what were the others for? dont remember..
      #setup_requires=requirements,
      #requires=requirements,

      # stuff for unitary test with pytest
      tests_require=['nose>=1.0'],
      # extras_require={'testing': ['pytest']},
	  test_suite='nose.collector',
      # install options
      cmdclass={'test': PyTest,
                'fpga': compile_fpga,
                'server': compile_server}
      )