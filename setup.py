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

# path to the directory that contains the setup.py script
SETUP_PATH = os.path.dirname(os.path.abspath(__file__))

def read(fname):
    return open(os.path.join(SETUP_PATH, fname)).read()

# Version info -- read without importing
_locals = {}
exec(read(os.path.join('pyrpl', '_version.py')), None, _locals)
version = _locals['__version__']

# # read requirements
# # from http://stackoverflow.com/questions/14399534/how-can-i-reference-requirements-txt-for-the-install-requires-kwarg-in-setuptool
# requirements = []
# here = os.path.abspath(os.path.dirname(__file__))
# with open(os.path.join(here, 'readthedocs_requirements.txt')) as f:
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
                'PyQt5<=5.14',  # cannot be installed with pip
                'qtpy<=1.9',  # qtpy 1.11 contains breaking API changes related to pyqtSignals
                'ipykernel>=5,<6',  # otherwise jupyter breaks
                'nbconvert',
                'jupyter-client']
if sys.version_info >= (3,4):  # python version dependencies
    requirements += ['quamash']
else:  # python 2.7
    requirements += ['futures', 'mock']  # mock is now a full dependency
if os.environ.get('TRAVIS') == 'true':
    requirements += ['pandoc']
if os.environ.get('READTHEDOCS') == 'True':
    requirements += ['pandoc', 'sphinx', 'sphinx_bootstrap_theme']  # mock is needed on readthedocs.io to mock PyQt5
    # remove a few of the mocked modules
    def rtd_included(r):
        for rr in ['numpy', 'scipy', 'pandas', 'scp', 'paramiko', 'nose',
                   'quamash', 'qtpy', 'asyncio', 'pyqtgraph']:
            if r.startswith(rr):
                return False
        return True
    requirements = [r for r in requirements if rtd_included(r)]

# cannot install pyQt4 with pip:
# http://stackoverflow.com/questions/4628519/is-it-possible-to-require-pyqt-from-setuptools-setup-py
# PyQt4
try:
    long_description = read('README.rst')
except:
    try:
        import pypandoc
        long_description = pypandoc.convert_file('README.md', 'rst')
    except:
        long_description = read('README.md')

def find_packages():
    """
    Simple function to find all modules under the current folder.
    """
    modules = []
    for dirpath, _, filenames in os.walk(os.path.join(SETUP_PATH, "pyrpl")):
        if "__init__.py" in filenames:
            modules.append(os.path.relpath(dirpath, SETUP_PATH))
    return [module.replace(os.sep, ".") for module in modules]


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
      long_description=long_description,
      author='Leonhard Neuhaus',
      author_email='neuhaus@lkb.upmc.fr',
      url='http://lneuhaus.github.io/pyrpl/',
      license='GPLv3',
      classifiers=['Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6',
                   'Programming Language :: C',
                   'Natural Language :: English',
                   'Development Status :: 4 - Beta',
                   'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                   'Topic :: Scientific/Engineering :: Human Machine Interfaces',
                   'Topic :: Scientific/Engineering :: Physics'],
      keywords='RedPitaya DSP FPGA IIR PDH synchronous detection filter PID '
               'control lockbox servo feedback lock quantum optics',
      platforms='any',
      packages=find_packages(), #['pyrpl'],
      package_data={'pyrpl': ['fpga/*',
                              'monitor_server/*',
                              'config/*',
                              'widgets/images/*']},
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
